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

import logging
import os
import pathlib
import tempfile
import time
from hashlib import md5

import numpy as np
import pydicom_seg
import SimpleITK
from dicomweb_client import DICOMwebClient
from monai.data import write_nifti
from monai.transforms import LoadImage
from pydicom.filereader import dcmread

from monailabel.utils.datastore.dicom.colors import GENERIC_ANATOMY_COLORS
from monailabel.utils.others.generic import run_command
from monailabel.utils.others.writer import write_itk

logger = logging.getLogger(__name__)


def generate_key(patient_id: str, study_id: str, series_id: str):
    return md5(f"{patient_id}+{study_id}+{series_id}".encode("utf-8")).hexdigest()


def binary_to_image(reference_image, label, dtype=np.uint16, file_ext=".nii.gz", use_itk=True):
    image_np, meta_dict = LoadImage()(reference_image)
    label_np = np.fromfile(label, dtype=dtype)

    logger.info(f"Image: {image_np.shape}")
    logger.info(f"Label: {label_np.shape}")

    label_np = label_np.reshape(image_np.shape, order="F")
    logger.info(f"Label (reshape): {label_np.shape}")

    output_file = tempfile.NamedTemporaryFile(suffix=file_ext).name
    affine = meta_dict.get("affine")
    if use_itk:
        write_itk(label_np, output_file, affine=affine, dtype=None, compress=True)
    else:
        write_nifti(label_np, output_file, affine=affine)
    return output_file


def nifti_to_dicom_seg(series_dir, label, label_info, ext="*"):
    label_np, meta_dict = LoadImage()(label)
    unique_labels = np.unique(label_np.flatten()).astype(np.int)
    unique_labels = unique_labels[unique_labels != 0]

    segment_attributes = []
    for i, idx in enumerate(unique_labels):
        info = label_info[i] if label_info and i < len(label_info) else {}
        name = info.get("name", "unknown")
        description = info.get("description", "Unknown")
        rgb = list(info.get("color", GENERIC_ANATOMY_COLORS.get(name, (255, 0, 0))))[0:3]

        logger.info(f"{i} => {idx} => {name}")

        segment_attribute = info.get(
            "segmentAttribute",
            {
                "labelID": int(1),
                "SegmentLabel": name,
                "SegmentDescription": description,
                "SegmentAlgorithmType": "AUTOMATIC",
                "SegmentAlgorithmName": "MONAILABEL",
                "SegmentedPropertyCategoryCodeSequence": {
                    "CodeValue": "123037004",
                    "CodingSchemeDesignator": "SCT",
                    "CodeMeaning": "Anatomical Structure",
                },
                "SegmentedPropertyTypeCodeSequence": {
                    "CodeValue": "78961009",
                    "CodingSchemeDesignator": "SCT",
                    "CodeMeaning": name,
                },
                "recommendedDisplayRGBValue": rgb,
            },
        )
        segment_attributes.append(segment_attribute)

    template = {
        "ContentCreatorName": "Reader1",
        "ClinicalTrialSeriesID": "Session1",
        "ClinicalTrialTimePointID": "1",
        "SeriesDescription": "Segmentation",
        "SeriesNumber": "300",
        "InstanceNumber": "1",
        "segmentAttributes": [segment_attributes],
        "ContentLabel": "SEGMENTATION",
        "ContentDescription": "MONAI Label - Image segmentation",
        "ClinicalTrialCoordinatingCenterName": "MONAI",
        "BodyPartExamined": "",
    }

    template = pydicom_seg.template.from_dcmqi_metainfo(template)
    writer = pydicom_seg.MultiClassWriter(
        template=template,
        inplane_cropping=False,
        skip_empty_slices=True,
        skip_missing_segment=False,
    )

    # Read source Images
    series_dir = pathlib.Path(series_dir)
    image_files = series_dir.glob(ext)
    image_datasets = [dcmread(str(f), stop_before_pixels=True) for f in image_files]
    logger.info(f"Total Source Images: {len(image_datasets)}")

    mask = SimpleITK.ReadImage(label)
    output_file = tempfile.NamedTemporaryFile(suffix=".dcm").name
    dcm = writer.write(mask, image_datasets)
    dcm.save_as(output_file)
    return output_file


def get_scu(query, output_dir, query_level="SERIES", host="127.0.0.1", port="4242", aet="MONAILABEL"):
    start = time.time()
    field = "StudyInstanceUID" if query_level == "STUDIES" else "SeriesInstanceUID"
    run_command(
        "python",
        [
            "-m",
            "pynetdicom",
            "getscu",
            host,
            port,
            "-P",
            "-k",
            f"0008,0052={query_level}",
            "-k",
            f"{field}={query}",
            "-aet",
            aet,
            "-q",
            "-od",
            output_dir,
        ],
    )
    logger.info(f"Time to run GET-SCU: {time.time() - start} (sec)")


def score_scu(input, host="127.0.0.1", port="4242", aet="MONAILABEL"):
    start = time.time()
    inputs = input if isinstance(input, list) else [input]
    for i in inputs:
        run_command("python", ["-m", "pynetdicom", "storescu", host, port, "-aet", aet, i])
    logger.info(f"Time to run GET-SCU: {time.time() - start} (sec)")


def dicom_web_download_series(study_id, series_id, save_dir, url="http://127.0.0.1:8042/dicom-web"):
    start = time.time()

    os.makedirs(save_dir, exist_ok=True)
    client = DICOMwebClient(url=url)
    instances = client.retrieve_series(study_id, series_id)
    for instance in instances:
        instance_id = instance.SOPInstanceUID
        file_name = os.path.join(save_dir, f"{instance_id}.dcm")
        instance.save_as(file_name)

    logger.info(f"Time to download: {time.time() - start} (sec)")


def dicom_web_upload_dcm(input, url="http://127.0.0.1:8042/dicom-web"):
    start = time.time()
    dataset = dcmread(input)

    client = DICOMwebClient(url=url)
    client.store_instances([dataset])
    logger.info(f"Time to save: {time.time() - start} (sec)")
