# MONAILabel

[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI Build](https://github.com/Project-MONAI/MONAILabel/workflows/build/badge.svg?branch=main)](https://github.com/Project-MONAI/MONAILabel/commits/main)
[![Documentation Status](https://readthedocs.org/projects/monailabel/badge/?version=latest)](https://docs.monai.io/projects/label/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/Project-MONAI/MONAILabel/branch/main/graph/badge.svg)](https://codecov.io/gh/Project-MONAI/MONAILabel)
[![PyPI version](https://badge.fury.io/py/monailabel-weekly.svg)](https://badge.fury.io/py/monailabel-weekly)

MONAILabel is a server-client system that facilitates interactive medical image annotation by using AI. It is an
open-source and easy-to-install ecosystem that can run locally on a machine with one or two GPUs. Both server and client
work on the same/different machine. However, initial support for multiple users is restricted. It shares the same
principles with [MONAI](https://github.com/Project-MONAI).

[Brief Demo](https://youtu.be/gzAR-Ix31Gs)

<img src="https://raw.githubusercontent.com/Project-MONAI/MONAILabel/main/docs/images/demo.png" width="800"/>

## Features
> _The codebase is currently under active development._

- framework for developing and deploying MONAILabel Apps to train and infer AI models
- compositional & portable APIs for ease of integration in existing workflows
- customizable design for varying user expertise
- 3DSlicer support


## Installation
MONAILabel supports following OS with GPU/CUDA enabled.
 - Ubuntu
 - Windows

To install the current release, you can simply run:

```bash
  pip install monailabel
```

For other installation methods (using the default GitHub branch, using Docker, etc.), please refer to the [installation guide](https://docs.monai.io/projects/label/en/latest/installation.html).

> Once you start the MONAILabel Server, by default it will be up and serving at http://127.0.0.1:8000/. Open the serving
  URL in browser. It will provide you the list of Rest APIs available.

### 3D Slicer

Download Preview Release from https://download.slicer.org/ and install MONAILabel plugin from Slicer Extension Manager.

Refer [3D Slicer plugin](plugins/slicer) for other options to install and run MONAILabel plugin in 3D Slicer.

## Contributing
For guidance on making a contribution to MONAILabel, see the [contributing guidelines](CONTRIBUTING.md).

## Community
Join the conversation on Twitter [@ProjectMONAI](https://twitter.com/ProjectMONAI) or join our [Slack channel](https://forms.gle/QTxJq3hFictp31UM9).

Ask and answer questions over on [MONAILabel's GitHub Discussions tab](https://github.com/Project-MONAI/MONAILabel/discussions).

## Links
- Website: https://monai.io/
- API documentation: https://docs.monai.io/projects/label
- Code: https://github.com/Project-MONAI/MONAILabel
- Project tracker: https://github.com/Project-MONAI/MONAILabel/projects
- Issue tracker: https://github.com/Project-MONAI/MONAILabel/issues
- Wiki: https://github.com/Project-MONAI/MONAILabel/wiki
- Test status: https://github.com/Project-MONAI/MONAILabel/actions
- PyPI package: https://pypi.org/project/monailabel/
- Weekly previews: https://pypi.org/project/monailabel-weekly/
- Docker Hub: https://hub.docker.com/r/projectmonai/monailabel
