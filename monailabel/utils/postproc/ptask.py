import copy
import logging
import os
import time
from abc import abstractmethod

import torch

from monailabel.interfaces.exception import MONAILabelError, MONAILabelException
from monailabel.utils.others.writer import Writer

logger = logging.getLogger(__name__)


class PostProcType:
    CRF = 'CRF'
    OTHERS = 'others'
    KNOWN_TYPES = [CRF, OTHERS]


class PostProcessingTask:
    """
    Basic Post Processing Task Helper
    """

    def __init__(self, method, type: PostProcType, labels, dimension, description):
        self.method = method
        self.type = type
        self.labels = labels
        self.dimension = dimension
        self.description = description

        self._methods = {}

    def info(self):
        return {
            "type": self.type,
            "labels": self.labels,
            "dimension": self.dimension,
            "description": self.description,
        }
    
    @abstractmethod
    def pre_transforms(self):
        """
        Provide List of pre-transforms

            For Example::

                return [
                    monai.transforms.LoadImaged(keys='image'),
                    monai.transforms.AddChanneld(keys='image'),
                    monai.transforms.Spacingd(keys='image', pixdim=[1.0, 1.0, 1.0]),
                    monai.transforms.ScaleIntensityRanged(keys='image',
                        a_min=-57, a_max=164, b_min=0.0, b_max=1.0, clip=True),
                ]

        """
        pass

    @abstractmethod
    def post_transforms(self):
        """
        Provide List of post-transforms

            For Example::

                return [
                    monai.transforms.AddChanneld(keys='pred'),
                    monai.transforms.Activationsd(keys='pred', softmax=True),
                    monai.transforms.AsDiscreted(keys='pred', argmax=True),
                    monai.transforms.SqueezeDimd(keys='pred', dim=0),
                    monai.transforms.ToNumpyd(keys='pred'),
                    monailabel.interface.utils.Restored(keys='pred', ref_image='image'),
                    monailabel.interface.utils.ExtremePointsd(keys='pred', result='result', points='points'),
                    monailabel.interface.utils.BoundingBoxd(keys='pred', result='result', bbox='bbox'),
                ]

        """
        pass

    @abstractmethod
    def postprocessor(self):
        """
        Provide postprocessor Class

            For Example::

                return monai.networks.blocks.CRF(
                    iterations, 
                    bilateral_weight,
                    gaussian_weight,
                    bilateral_spatial_sigma,
                    bilateral_color_sigma,
                    gaussian_spatial_sigma,
                    compatibility_kernel_range
                    )
        """
        pass

    def run_postprocessor(self, data, postprocessor):
        return postprocessor(data)

    def __call__(self, request):
        """
        It provides basic implementation to run the following in order
            - Run Pre Transforms
            - Run PostProcessor
            - Run Post Transforms
            - Run Writer to save the label mask and result params

        Returns: Label (File Path) and Result Params (JSON)
        """
        begin = time.time()

        data = copy.deepcopy(request)
        data.update({'image_path': request.get('image')})
        device = request.get('device', 'cuda')

        start = time.time()
        data = self.run_pre_transforms(data, self.pre_transforms())
        latency_pre = time.time() - start

        start = time.time()
        data = self.run_postprocessor(data, self.postprocessor())
        latency_postproc = time.time() - start

        start = time.time()
        data = self.run_post_transforms(data, self.post_transforms())
        latency_post = time.time() - start

        start = time.time()
        result_file_name, result_json = self.writer(data)
        latency_write = time.time() - start

        latency_total = time.time() - begin
        logger.info(
            "++ Latencies => Total: {:.4f}; Pre: {:.4f}; Postprocessor: {:.4f}; Post: {:.4f}; Write: {:.4f}".format(
                latency_total, latency_pre, latency_postproc, latency_post, latency_write))

        logger.info('Result File: {}'.format(result_file_name))
        logger.info('Result Json: {}'.format(result_json))
        return result_file_name, result_json

    def run_pre_transforms(self, data, transforms):
        return self.run_transforms(data, transforms, log_prefix='PRE')

    def run_post_transforms(self, data, transforms):
        return self.run_transforms(data, transforms, log_prefix='POST')

    def writer(self, data, label='pred', text='result', extension=None, dtype=None):
        """
        You can provide your own writer.  However this writer saves the prediction/label mask to file
        and fetches result json

        :param data: typically it is post processed data
        :param label: label that needs to be written
        :param text: text field from data which represents result params
        :param extension: output label extension
        :param dtype: output label dtype
        :return: tuple of output_file and result_json
        """
        logger.info('Writing Result')
        if extension is not None:
            data['result_extension'] = extension
        if dtype is not None:
            data['result_dtype'] = dtype

        writer = Writer(label=label, json=text)
        return writer(data)

    @staticmethod
    def dump_data(data):
        if logging.getLogger().level == logging.DEBUG:
            logger.debug('**************************** DATA ********************************************')
            for k in data:
                v = data[k]
                logger.debug('Data key: {} = {}'.format(
                    k,
                    v.shape if hasattr(v, 'shape') else v if type(v) in (
                        int, float, bool, str, dict, tuple, list) else type(v)))
            logger.debug('******************************************************************************')

    @staticmethod
    def _shape_info(data, keys=('image', 'label', 'pred', 'model', 'logits', 'unary')):
        shape_info = []
        for key in keys:
            val = data.get(key)
            if val is not None and hasattr(val, 'shape'):
                shape_info.append('{}: {}'.format(key, val.shape))
        return '; '.join(shape_info)

    @staticmethod
    def run_transforms(data, transforms, log_prefix='POST'):
        """
        Run Transforms

        :param data: Input data dictionary
        :param transforms: List of transforms to run
        :param log_prefix: Logging prefix (POST or PRE)
        :return: Processed data after running transforms
        """
        logger.info('{} - Run Transforms'.format(log_prefix))
        logger.info('{} - Input Keys: {}'.format(log_prefix, data.keys()))

        if not transforms:
            return data

        for t in transforms:
            name = t.__class__.__name__
            start = time.time()

            PostProcessingTask.dump_data(data)
            if callable(t):
                data = t(data)
            else:
                raise MONAILabelException(MONAILabelError.POSTPROC_ERROR, "Transformer '{}' is not callable".format(
                    t.__class__.__name__))

            logger.info("{} - Transform ({}): Time: {:.4f}; {}".format(
                log_prefix, name, float(time.time() - start), PostProcessingTask._shape_info(data)))
            logger.debug('-----------------------------------------------------------------------------')

        PostProcessingTask.dump_data(data)
        return data
