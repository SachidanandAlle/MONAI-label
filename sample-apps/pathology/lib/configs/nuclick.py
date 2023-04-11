# Copyright (c) MONAI Consortium
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
from typing import Any, Dict, Optional, Union

import lib.infers
import lib.trainers
from monai.bundle import download, get_bundle_versions

from monailabel.interfaces.config import TaskConfig
from monailabel.interfaces.tasks.infer_v2 import InferTask
from monailabel.interfaces.tasks.train import TrainTask
from monailabel.config import settings

logger = logging.getLogger(__name__)


class NuClick(TaskConfig):
    def init(self, name: str, model_dir: str, conf: Dict[str, str], planner: Any, **kwargs):
        super().init(name, model_dir, conf, planner, **kwargs)

        bundle_name = "pathology_nuclick_annotation"
        repo_owner, repo_name, tag_name = "Project-MONAI/model-zoo/hosting_storage_v1".split("/")
        auth_token = conf.get("auth_token", settings.MONAI_ZOO_AUTH_TOKEN) if conf.get("auth_token", settings.MONAI_ZOO_AUTH_TOKEN) else None
        bundle_version = get_bundle_versions(bundle_name, repo=f"{repo_owner}/{repo_name}", tag=tag_name, auth_token=auth_token)[
            "latest_version"
        ]

        self.bundle_path = os.path.join(self.model_dir, bundle_name)
        if not os.path.exists(self.bundle_path):
            download(name=bundle_name, version=bundle_version, bundle_dir=self.model_dir)

    def infer(self) -> Union[InferTask, Dict[str, InferTask]]:
        task: InferTask = lib.infers.NuClick(self.bundle_path, self.conf)
        return task

    def trainer(self) -> Optional[TrainTask]:
        task: TrainTask = lib.trainers.NuClick(self.bundle_path, self.conf)
        return task
