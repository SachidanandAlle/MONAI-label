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
from distutils.util import strtobool

from lib import MyInfer, MyTrain
from lib.activelearning import MyStrategy
from monai.apps import load_from_mmar

from monailabel.interfaces.app import MONAILabelApp
from monailabel.utils.activelearning.random import Random
from monailabel.utils.activelearning.tta import TTAStrategy
from monailabel.utils.scoring.dice import Dice
from monailabel.utils.scoring.sum import Sum
from monailabel.utils.scoring.tta import TTAScoring

logger = logging.getLogger(__name__)


class MyApp(MONAILabelApp):
    def __init__(self, app_dir, studies, conf):
        self.model_dir = os.path.join(app_dir, "model")
        self.final_model = os.path.join(self.model_dir, "model.pt")

        self.mmar = "clara_pt_spleen_ct_segmentation_1"

        self.tta_enabled = strtobool(conf.get("tta_enabled", "false"))
        self.tta_samples = int(conf.get("tta_samples", "5"))
        logger.info(f"TTA Enabled: {self.tta_enabled}; Samples: {self.tta_samples}")

        super().__init__(
            app_dir=app_dir,
            studies=studies,
            conf=conf,
            name="Segmentation - Spleen",
            description="Active Learning solution to label Spleen Organ over 3D CT Images",
        )

    def init_infers(self):
        infers = {
            "segmentation_spleen": MyInfer(self.final_model, load_from_mmar(self.mmar, self.model_dir)),
        }

        # Simple way to Add deepgrow 2D+3D models for infer tasks
        infers.update(self.deepgrow_infer_tasks(self.model_dir))
        return infers

    def init_trainers(self):
        return {
            "segmentation_spleen": MyTrain(
                self.model_dir, load_from_mmar(self.mmar, self.model_dir), publish_path=self.final_model
            )
        }

    def init_strategies(self):
        return {
            "TTA": TTAStrategy(),
            "random": Random(),
            "first": MyStrategy(),
        }

    def init_scoring_methods(self):
        return {
            "TTA": TTAScoring(
                model=self.final_model,
                network=load_from_mmar(self.mmar, self.model_dir),
                deepedit=False,
                num_samples=self.tta_samples,
            ),
            "sum": Sum(),
            "dice": Dice(),
        }

    def on_init_complete(self):
        super().on_init_complete()
        self._run_tta_scoring()

    def next_sample(self, request):
        res = super().next_sample(request)
        self._run_tta_scoring()
        return res

    def train(self, request):
        res = super().train(request)
        self._run_tta_scoring()
        return res

    def _run_tta_scoring(self):
        if self.tta_enabled:
            self.async_scoring("TTA")
