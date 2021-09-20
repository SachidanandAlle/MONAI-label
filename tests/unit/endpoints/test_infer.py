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

import json
import unittest

import torch

from .context import BasicEndpointTestSuite


class EndPointInfer(BasicEndpointTestSuite):
    def test_segmentation(self):

        model = "deepedit_seg"
        image = "la_003"

        response = self.client.post(f"/infer/{model}?image={image}")
        assert response.status_code == 200

    def test_deepedit(self):

        model = "deepedit"
        image = "la_003"
        params = {"foreground": [[153, 175, 60]], "background": []}

        response = self.client.post(f"/infer/{model}?image={image}", data={"params": json.dumps(params)})
        assert response.status_code == 200


if __name__ == "__main__":
    unittest.main()
