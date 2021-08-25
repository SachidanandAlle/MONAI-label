# Copyright 2020 - 2021 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import copy
import fnmatch
import io
import json
import logging
import os
import pathlib
import shutil
import time
from typing import Any, Dict, List

from filelock import FileLock
from pydantic import BaseModel
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

from monailabel.interfaces.datastore import Datastore, DefaultLabelTag
from monailabel.interfaces.exception import ImageNotFoundException, LabelNotFoundException
from monailabel.utils.others.generic import file_checksum

logger = logging.getLogger(__name__)


class DataModel(BaseModel):
    id: str
    ext: str = ""
    info: Dict[str, Any] = {}

    def path(self):
        return self.id + self.ext


class ImageLabelModel(BaseModel):
    image: DataModel
    labels: Dict[str, DataModel] = {}  # tag => label

    def label(self, id):
        for tag, label in self.labels.items():
            if label.id == id:
                return tag, label
        return None, None

    def tags(self):
        return self.labels.keys()


class LocalDatastoreModel(BaseModel):
    name: str
    description: str
    images_dir: str = "."
    labels_dir: str = "labels"
    objects: Dict[str, ImageLabelModel] = {}

    # will be ignored while saving...
    base_path: str = ""

    def tags(self):
        tags = set()
        for v in self.objects.values():
            tags.update(v.tags())
        return tags

    def filter_by_tag(self, tag: str):
        return [obj for obj in self.objects.values() if obj.labels.get(tag)]

    def filter_by_id(self, id: str):
        return [obj for obj in self.objects.values() if obj.label(id)]

    def label(self, id: str):
        objects = self.filter_by_id(id)
        obj = next(iter(objects)) if objects else None
        if obj:
            return obj.label(id)
        return None, None

    def image_path(self):
        return os.path.join(self.base_path, self.images_dir) if self.base_path else self.images_dir

    def label_path(self, tag):
        path = os.path.join(self.labels_dir, tag) if tag else self.labels_dir
        return os.path.join(self.base_path, path) if self.base_path else path

    def labels_path(self):
        path = self.labels_dir
        return {tag: os.path.join(path, tag) if self.base_path else path for tag in self.tags()}

    def datalist(self, tag: str) -> List[Dict[str, str]]:
        image_path = self.image_path()
        label_path = self.label_path(tag)

        items = []
        for obj in self.filter_by_tag(tag):
            items.append(
                {
                    "image": os.path.realpath(os.path.join(image_path, obj.image.path())),
                    "label": os.path.realpath(os.path.join(label_path, obj.labels[tag].path())),
                }
            )
        return items


class LocalDatastore(Datastore):
    """
    Class to represent a datastore local to the MONAI-Label Server

    Attributes
    ----------
    `name: str`
        The name of the datastore

    `description: str`
        The description of the datastore
    """

    def __init__(
        self,
        datastore_path: str,
        images_dir: str = ".",
        labels_dir: str = "labels",
        datastore_config: str = "datastore_v2.json",
        extensions=("*.nii.gz", "*.nii"),
        auto_reload=False,
    ):
        """
        Creates a `LocalDataset` object

        Parameters:

        `datastore_path: str`
            a string to the directory tree of the desired dataset

        `datastore_config: str`
            optional file name of the dataset configuration file (by default `dataset.json`)
        """
        self._datastore_path = datastore_path
        self._datastore_config_path = os.path.join(datastore_path, datastore_config)
        self._extensions = [extensions] if isinstance(extensions, str) else extensions
        self._ignore_event_count = 0
        self._ignore_event_config = False
        self._config_ts = 0
        self._auto_reload = auto_reload

        logging.getLogger("filelock").setLevel(logging.ERROR)

        logger.info(f"Extensions: {self._extensions}")
        logger.info(f"Auto Reload: {auto_reload}")

        os.makedirs(os.path.join(self._datastore_path), exist_ok=True)

        self._lock = FileLock(os.path.join(datastore_path, ".lock"))
        self._datastore: LocalDatastoreModel = LocalDatastoreModel(
            name="new-dataset", description="New Dataset", images_dir=images_dir, labels_dir=labels_dir
        )
        self._init_from_datastore_file(throw_exception=True)
        self._datastore.base_path = self._datastore_path

        os.makedirs(self._datastore.image_path(), exist_ok=True)
        os.makedirs(self._datastore.label_path(None), exist_ok=True)
        os.makedirs(self._datastore.label_path(DefaultLabelTag.FINAL), exist_ok=True)
        os.makedirs(self._datastore.label_path(DefaultLabelTag.ORIGINAL), exist_ok=True)

        # reconcile the loaded datastore file with any existing files in the path
        self._reconcile_datastore()

        if auto_reload:
            logger.info("Start observing external modifications on datastore (AUTO RELOAD)")
            # Image Dir
            include_patterns = [f"{self._datastore.image_path()}{os.path.sep}{ext}" for ext in [*extensions]]

            # Label Dir(s)
            label_dirs = self._datastore.labels_path()
            label_dirs[DefaultLabelTag.FINAL] = self._datastore.label_path(DefaultLabelTag.FINAL)
            label_dirs[DefaultLabelTag.ORIGINAL] = self._datastore.label_path(DefaultLabelTag.ORIGINAL)
            for label_dir in label_dirs.values():
                include_patterns.extend(f"{label_dir}{os.path.sep}{ext}" for ext in [*extensions])

            # Config
            include_patterns.append(self._datastore_config_path)

            self._handler = PatternMatchingEventHandler(patterns=include_patterns)
            self._handler.on_created = self._on_any_event
            self._handler.on_deleted = self._on_any_event
            self._handler.on_modified = self._on_modify_event

            try:
                self._ignore_event_count = 0
                self._ignore_event_config = False
                self._observer = Observer()
                self._observer.schedule(self._handler, recursive=True, path=self._datastore_path)
                self._observer.start()
            except OSError as e:
                logger.error(
                    "Failed to start File watcher. "
                    "Local datastore will not update if images and labels are moved from datastore location."
                )
                logger.error(str(e))

    def name(self) -> str:
        """
        Dataset name (if one is assigned)

        Returns:
            name (str): Dataset name as string
        """
        return self._datastore.name

    def set_name(self, name: str):
        """
        Sets the dataset name in a standardized format (lowercase, no spaces).

            Parameters:
                name (str): Desired dataset name
        """
        self._datastore.name = name
        self._update_datastore_file()

    def description(self) -> str:
        """
        Gets the description field for the dataset

        :return description: str
        """
        return self._datastore.description

    def set_description(self, description: str):
        """
        Set a description for the dataset

        :param description: str
        """
        self._datastore.description = description
        self._update_datastore_file()

    def datalist(self, full_path=True) -> List[Dict[str, str]]:
        """
        Return a dictionary of image and label pairs corresponding to the 'image' and 'label'
        keys respectively

        :return: the {'label': image, 'label': label} pairs for training
        """
        ds = self._datastore.datalist(DefaultLabelTag.FINAL)
        if not full_path:
            ds = json.loads(json.dumps(ds).replace(f"{self._datastore_path.rstrip(os.pathsep)}{os.pathsep}", ""))
        return ds

    def to_bytes(self, file):
        return io.BytesIO(pathlib.Path(file).read_bytes())

    def get_image(self, image_id: str) -> Any:
        """
        Retrieve image object based on image id

        :param image_id: the desired image's id
        :return: return the "image"
        """
        obj = self._datastore.objects.get(image_id)
        return self.to_bytes(os.path.join(self._datastore.image_path(), obj.image.path())) if obj else None

    def get_image_uri(self, image_id: str) -> str:
        """
        Retrieve image uri based on image id

        :param image_id: the desired image's id
        :return: return the image uri
        """
        obj = self._datastore.objects.get(image_id)
        return str(os.path.realpath(os.path.join(self._datastore.image_path(), obj.image.path()))) if obj else ""

    def get_image_info(self, image_id: str) -> Dict[str, Any]:
        """
        Get the image information for the given image id

        :param image_id: the desired image id
        :return: image info as a list of dictionaries Dict[str, Any]
        """
        obj = self._datastore.objects.get(image_id)
        info = copy.deepcopy(obj.image.info) if obj else {}
        if obj:
            path = os.path.join(self._datastore.image_path(), obj.image.path())
            info.update(
                {
                    "checksum": file_checksum(path),
                    "name": obj.image.path(),
                    "path": path,
                }
            )
        return info

    def get_label(self, label_id: str) -> Any:
        """
        Retrieve image object based on label id

        :param label_id: the desired label's id
        :return: return the "label"
        """
        tag, label = self._datastore.label(label_id)
        return self.to_bytes(os.path.join(self._datastore.label_path(tag), label.path())) if tag else None

    def get_label_uri(self, label_id: str) -> str:
        """
        Retrieve label uri based on image id

        :param label_id: the desired label's id
        :return: return the label uri
        """
        tag, label = self._datastore.label(label_id)
        return str(os.path.realpath(os.path.join(self._datastore.label_path(tag), label.path()))) if tag else ""

    def get_labels_by_image_id(self, image_id: str) -> Dict[str, str]:
        """
        Retrieve all label ids for the given image id

        :param image_id: the desired image's id
        :return: label ids mapped to the appropriate `LabelTag` as Dict[str, LabelTag]
        """
        obj = self._datastore.objects.get(image_id)
        if obj:
            return {label.id: tag for tag, label in obj.labels.items()}
        return {}

    def get_label_by_image_id(self, image_id: str, tag: str) -> str:
        """
        Retrieve label id for the given image id and tag

        :param image_id: the desired image's id
        :param tag: matching tag name
        :return: label id
        """
        obj = self._datastore.objects.get(image_id)
        label = obj.labels.get(tag) if obj else None
        return label.id if label else ""

    def get_label_info(self, label_id: str) -> Dict[str, Any]:
        """
        Get the label information for the given label id

        :param label_id: the desired label id
        :return: label info as a list of dictionaries Dict[str, Any]
        """
        _, label = self._datastore.label(label_id)
        info: Dict[str, Any] = label.info if label else {}
        return info

    def get_labeled_images(self) -> List[str]:
        """
        Get all images that have a corresponding label

        :return: list of image ids List[str]
        """
        return [obj.image.id for obj in self._datastore.objects.values() if obj.labels.get(DefaultLabelTag.FINAL)]

    def get_unlabeled_images(self) -> List[str]:
        """
        Get all images that have no corresponding label

        :return: list of image ids List[str]
        """
        return [obj.image.id for obj in self._datastore.objects.values() if not obj.labels.get(DefaultLabelTag.FINAL)]

    def list_images(self) -> List[str]:
        """
        Return list of image ids available in the datastore

        :return: list of image ids List[str]
        """
        return list(self._datastore.objects.keys())

    def _on_any_event(self, event):
        if self._ignore_event_count:
            logger.debug(f"Ignoring event by count: {self._ignore_event_count} => {event}")
            self._ignore_event_count = max(self._ignore_event_count - 1, 0)
            return

        logger.debug(f"Event: {event}")
        self.refresh()

    def _on_modify_event(self, event):
        # handle modify events only for config path; rest ignored
        if event.src_path != self._datastore_config_path:
            return

        if self._ignore_event_config:
            self._ignore_event_config = False
            return

        self._init_from_datastore_file()

    def refresh(self):
        """
        Refresh the datastore based on the state of the files on disk
        """
        self._init_from_datastore_file()
        self._reconcile_datastore()

    def add_image(self, image_id: str, image_filename: str) -> str:
        image_ext = "".join(pathlib.Path(image_filename).suffixes)
        if not image_id:
            image_id = os.path.basename(image_filename).replace(image_ext, "")

        logger.info(f"Adding Image: {image_id} => {image_filename}")
        dest = os.path.join(self._datastore.image_path(), image_id + image_ext)
        if os.path.isdir(image_filename):
            shutil.copytree(image_filename, dest)
        else:
            shutil.copy(image_filename, dest)

        if not self._auto_reload:
            self.refresh()
        return image_id

    def remove_image(self, image_id: str) -> None:
        logger.info(f"Removing Image: {image_id}")

        # Remove all labels
        label_ids = self.get_labels_by_image_id(image_id)
        for label_id in label_ids:
            self.remove_label(label_id)

        # Remove Image
        obj = self._datastore.objects.get(image_id)
        p = os.path.join(self._datastore.image_path(), obj.image.path()) if obj else None
        if p and os.path.exists(p):
            shutil.rmtree(p)

        if not self._auto_reload:
            self.refresh()

    def save_label(
        self, image_id: str, label_filename: str, label_tag: str, label_info: Dict[str, Any], label_id: str = ""
    ) -> str:
        """
        Save a label for the given image id and return the newly saved label's id

        :param image_id: the image id for the label
        :param label_filename: the path to the label file
        :param label_tag: the tag for the label
        :param label_info: additional info for the label
        :param label_id: use this label id instead of generating it from filename
        :return: the label id for the given label filename
        """
        logger.info(f"Saving Label for Image: {image_id}; Tag: {label_tag}")
        obj = self._datastore.objects.get(image_id)
        if not obj:
            raise ImageNotFoundException(f"Image {image_id} not found")

        label_ext = "".join(pathlib.Path(label_filename).suffixes)
        if not label_id:
            label_id = image_id
        else:
            label_id = f"{image_id}+{label_id}"

        logger.info(f"Adding Label: {label_id} => {label_filename}")
        label_path = self._datastore.label_path(label_tag)
        dest = os.path.join(label_path, label_id + label_ext)

        with self._lock:
            os.makedirs(label_path, exist_ok=True)
            if os.path.isdir(label_filename):
                shutil.copytree(label_filename, dest)
            else:
                shutil.copy(label_filename, dest)

            obj.labels[label_tag] = DataModel(id=label_id, info={"ts": int(time.time())}, ext=label_ext)
            self._update_datastore_file(lock=False)
        return label_id

    def remove_label(self, label_id: str) -> None:
        logger.info(f"Removing label: {label_id}")

        tag, label = self._datastore.label(label_id)
        p = os.path.join(self._datastore.label_path(tag), label.path()) if label else None
        if p and os.path.exists(p):
            shutil.rmtree(p)

        if not self._auto_reload:
            self.refresh()

    def remove_label_by_tag(self, label_tag: str) -> None:
        label_ids = [obj.labels[label_tag].id for obj in self._datastore.objects.values() if obj.labels.get(label_tag)]
        logger.info(f"Tag: {label_tag}; Removing label(s): {label_ids}")
        for label_id in label_ids:
            self.remove_label(label_id)

    def update_image_info(self, image_id: str, info: Dict[str, Any]) -> None:
        """
        Update (or create a new) info tag for the desired image

        :param image_id: the id of the image we want to add/update info
        :param info: a dictionary of custom image information Dict[str, Any]
        """
        obj = self._datastore.objects.get(image_id)
        if not obj:
            raise ImageNotFoundException(f"Image {image_id} not found")

        obj.image.info.update(info)
        self._update_datastore_file()

    def update_label_info(self, label_id: str, info: Dict[str, Any]) -> None:
        """
        Update (or create a new) info tag for the desired label

        :param label_id: the id of the label we want to add/update info
        :param info: a dictionary of custom label information Dict[str, Any]
        """
        _, label = self._datastore.label(label_id)
        if not label:
            raise LabelNotFoundException(f"Label {label_id} not found")

        label.info.update(info)
        self._update_datastore_file()

    def _list_files(self, path, patterns):
        files = os.listdir(path)

        filtered = dict()
        for pattern in patterns:
            matching = fnmatch.filter(files, pattern)
            for file in matching:
                filtered[os.path.basename(file)] = file
        return filtered

    def _reconcile_datastore(self):
        invalidate = 0
        invalidate += self._remove_non_existing()
        invalidate += self._add_non_existing_images()

        labels_dir = self._datastore.label_path(None)
        logger.info(f"Labels Dir {labels_dir}")
        tags = [f for f in os.listdir(labels_dir) if os.path.isdir(os.path.join(labels_dir, f))]
        logger.debug(f"Label Tags: {tags}")
        for tag in tags:
            invalidate += self._add_non_existing_labels(tag)

        invalidate += self._remove_non_existing()

        logger.debug(f"Invalidate count: {invalidate}")
        if invalidate:
            logger.debug("Save datastore file to disk")
            self._update_datastore_file()
        else:
            logger.debug("No changes needed to flush to disk")

    def _add_non_existing_images(self) -> int:
        invalidate = 0

        local_images = self._list_files(self._datastore.image_path(), self._extensions)

        image_ids = list(self._datastore.objects.keys())
        for image_file in local_images:
            image_ext = "".join(pathlib.Path(image_file).suffixes)
            image_id = image_file.replace(image_ext, "")

            if image_id not in image_ids:
                logger.info(f"Adding New Image: {image_id} => {image_file}")
                invalidate += 1
                self._datastore.objects[image_id] = ImageLabelModel(image=DataModel(id=image_id, ext=image_ext))

        return invalidate

    def _add_non_existing_labels(self, tag) -> int:
        invalidate = 0

        local_labels = self._list_files(self._datastore.label_path(tag), self._extensions)

        label_ids = [obj.labels[tag].id for obj in self._datastore.filter_by_tag(tag)]
        for label_file in local_labels:
            label_ext = "".join(pathlib.Path(label_file).suffixes)
            label_id = label_file.replace(label_ext, "")
            image_id = label_id.split("+")[0]

            if label_id not in label_ids:
                obj = self._datastore.objects.get(image_id)
                if not obj:
                    logger.warning(f"IGNORE:: No matching image '{image_id}' for '{label_id}' to add [{label_file}]")
                    continue

                logger.info(f"Adding New Label: {tag} => {label_id} => {label_file} for {image_id}")
                obj.labels[tag] = DataModel(id=label_id, ext=label_ext)
                invalidate += 1

        return invalidate

    def _remove_non_existing(self) -> int:
        invalidate = 0

        objects: Dict[str, ImageLabelModel] = {}
        for image_id, obj in self._datastore.objects.items():
            if not os.path.exists(os.path.join(self._datastore.image_path(), obj.image.path())):
                logger.info(f"Removing non existing Image Id: {image_id}")
                invalidate += 1
            else:
                labels: Dict[str, DataModel] = {}
                for tag, label in obj.labels.items():
                    if not os.path.exists(os.path.join(self._datastore.label_path(tag), label.path())):
                        logger.info(f"Removing non existing Label Id: '{label.id}' for '{tag}' for '{image_id}'")
                        invalidate += 1
                    else:
                        labels[tag] = label
                obj.labels.clear()
                obj.labels.update(labels)
                objects[image_id] = obj

        self._datastore.objects.clear()
        self._datastore.objects.update(objects)
        return invalidate

    def _init_from_datastore_file(self, throw_exception=False):
        try:
            with self._lock:
                if os.path.exists(self._datastore_config_path):
                    ts = os.stat(self._datastore_config_path).st_mtime
                    if self._config_ts != ts:
                        logger.debug(f"Reload Datastore; old ts: {self._config_ts}; new ts: {ts}")
                        self._datastore = LocalDatastoreModel.parse_file(self._datastore_config_path)
                        self._config_ts = ts
        except ValueError as e:
            logger.error(f"+++ Failed to load datastore => {e}")
            if throw_exception:
                raise e

    def _update_datastore_file(self, lock=True):
        if lock:
            self._lock.acquire()

        logger.debug("+++ Datastore is updated...")
        self._ignore_event_config = True
        with open(self._datastore_config_path, "w") as f:
            f.write(json.dumps(self._datastore.dict(exclude={"base_path"}), indent=2, default=str))
        self._config_ts = os.stat(self._datastore_config_path).st_mtime

        if lock:
            self._lock.release()

    def status(self) -> Dict[str, Any]:
        tags: dict = {}
        for obj in self._datastore.objects.values():
            for tag, _ in obj.labels.items():
                tags[tag] = tags.get(tag, 0) + 1

        return {
            "total": len(self.list_images()),
            "completed": len(self.get_labeled_images()),
            "label_tags": tags,
            "train": self.datalist(full_path=False),
        }

    def json(self):
        return self._datastore.dict(exclude={"base_path"})
