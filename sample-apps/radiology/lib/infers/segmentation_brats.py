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
from typing import Callable, Sequence

from monai.inferers import Inferer, SlidingWindowInferer
from monai.transforms import (
    Activationsd,
    AsDiscreted,
    EnsureChannelFirstd,
    EnsureTyped,
    LoadImaged,
    NormalizeIntensityd,
    ToNumpyd,
)

from monailabel.interfaces.tasks.infer import InferTask, InferType
from monailabel.transform.post import Restored


class SegmentationBrats(InferTask):
    """
    This provides Inference Engine for pre-trained segmentation (UNet) model over MSD Dataset.
    """

    def __init__(
        self,
        path,
        network=None,
        spatial_size=(128, 128, 128),
        type=InferType.SEGMENTATION,
        labels=None,
        dimension=3,
        description="A pre-trained model for volumetric (3D) segmentation over 3D Images",
        **kwargs,
    ):
        super().__init__(
            path=path,
            network=network,
            type=type,
            labels=labels,
            dimension=dimension,
            description=description,
            **kwargs,
        )
        self.spatial_size = spatial_size

    def pre_transforms(self, data=None) -> Sequence[Callable]:
        return [
            LoadImaged(keys="image", reader="ITKReader"),
            EnsureChannelFirstd(keys="image"),
            NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
            EnsureTyped(keys="image"),
        ]

    def inferer(self, data=None) -> Inferer:
        return SlidingWindowInferer(roi_size=self.spatial_size, sw_batch_size=1, overlap=0.6)

    def inverse_transforms(self, data=None):
        return []

    def post_transforms(self, data=None) -> Sequence[Callable]:
        return [
            EnsureTyped(keys="pred", device=data.get("device") if data else None),
            Activationsd(keys="pred", softmax=len(self.labels) > 1, sigmoid=len(self.labels) == 1),
            AsDiscreted(keys="pred", argmax=len(self.labels) > 1, threshold=0.5 if len(self.labels) == 1 else None),
            ToNumpyd(keys="pred"),
            Restored(keys="pred", ref_image="image"),
        ]
