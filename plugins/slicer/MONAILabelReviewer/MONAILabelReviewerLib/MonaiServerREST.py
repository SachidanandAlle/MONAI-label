import datetime
import logging
import os
import json
from urllib.parse import quote_plus

import requests
from requests.structures import CaseInsensitiveDict

"""
MonaiServerREST provides the REST endpoints to the MONAIServer
"""


class MonaiServerREST:
    def __init__(self, serverUrl: str):
        self.PARAMS_PREFIX_REST_REQUEST = 'params'
        self.serverUrl = serverUrl

    def getServerUrl(self) -> str:
        return self.serverUrl

    def getCurrentTime(self) -> datetime:
        return datetime.datetime.now()

    def requestDataStoreInfo(self) -> dict:
        download_uri = f"{self.serverUrl}/datastore/?output=all"

        try:
            response = requests.get(download_uri, timeout=5)
        except Exception as exception:
            logging.warning(f"{self.getCurrentTime()}: Request for DataStoreInfo failed due to '{exception}'")
            return None
        if response.status_code != 200:
            logging.warning(
                "{}: Request for datastore-info failed (url: '{}'). Response code is {}".format(
                    self.getCurrentTime(), download_uri, response.status_code
                )
            )
            return None

        return response.json()

    def getDicomDownloadUri(self, image_id: str) -> str:
        download_uri = f"{self.serverUrl}/datastore/image?image={quote_plus(image_id)}"
        logging.info(f"{self.getCurrentTime()}: REST: request dicom image '{download_uri}'")
        return download_uri

    def requestSegmentation(self, image_id: str, tag : str) -> requests.models.Response:
        if(tag == ''):
            tag = 'final'
        download_uri = f"{self.serverUrl}/datastore/label?label={quote_plus(image_id)}&tag={quote_plus(tag)}"
        logging.info(f"{self.getCurrentTime()}: REST: request segmentation '{download_uri}'")

        try:
            response = requests.get(download_uri, timeout=5)
        except Exception as exception:
            logging.warning(
                "{}: Segmentation request (image id: '{}') failed due to '{}'".format(
                    self.getCurrentTime(), image_id, exception
                )
            )
            return None
        if response.status_code != 200:
            logging.warn(
                "{}: Segmentation request (image id: '{}') failed due to response code: '{}'".format(
                    self.getCurrentTime(), image_id, response.status_code
                )
            )
            return None

        return response

    def checkServerConnection(self) -> bool:
        if not self.serverUrl:
            self.serverUrl = "http://127.0.0.1:8000"
        url = self.serverUrl.rstrip("/")

        try:
            response = requests.get(url, timeout=5)
        except Exception as exception:
            logging.warning(f"{self.getCurrentTime()}: Connection to Monai Server failed due to '{exception}'")
            return False
        if response.status_code != 200:
            logging.warn(
                "{}: Server connection Failed. (response code = {}) ".format(
                    self.getCurrentTime(), response.status_code
                )
            )
            return False

        logging.info(f"{self.getCurrentTime()}: Successfully connected to server (server url: '{url}').")
        return True

    def updateLabelInfo(self, image_id: str, params: dict) -> int:
        """
        the image_id is the unique ID of an radiographic image
        If the image has a label/segmentation, its label/label_id corresponds to its image_id
        """
        embeddedParams = self.embeddedLabelContentInParams(params)
        logging.warn("REST: {}".format(embeddedParams))
        url = f"{self.serverUrl}/datastore/updatelabelinfo?label_id={quote_plus(image_id)}"
        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["accept"] = "application/json"

        try:
            response = requests.put(url, headers=headers, data=embeddedParams)
        except Exception as exception:
            logging.warning(
                "{}: Update meta data (image id: '{}') failed due to '{}'".format(
                    self.getCurrentTime(), image_id, exception
                )
            )
            return None
        if (response.status_code != 200):
            logging.warn(
                "{}: Update meta data (image id: '{}') failed due to response code = {}) ".format(
                    self.getCurrentTime(), image_id, response.status_code
                )
            )
            return response.status_code

        logging.info(f"{self.getCurrentTime()}: Meta data was updated successfully (image id: '{image_id}').")
        return response.status_code

    def embeddedLabelContentInParams(self, labelContent : dict) -> dict:
        params = {}
        params[self.PARAMS_PREFIX_REST_REQUEST] = json.dumps(labelContent)
        return params

    def saveLabel(self, imageId : str , labelDirectory : str, tag : str, params : dict):
        if(params is not None):
            embeddedParams = self.embeddedLabelContentInParams(params)
        logging.info(f"{self.getCurrentTime()}: Label and Meta data (image id: '{imageId}'): '{embeddedParams}'")
        
        url = "http://localhost:8000/datastore/label?image={}".format(imageId)
        if tag:
            url += f"&tag={tag}"

        with open(os.path.abspath(labelDirectory), "rb") as f:
                response = requests.put(url, data=embeddedParams, files={"label": (imageId+".nrrd", f)})

        if(response.status_code == 200):
            logging.info(f"{self.getCurrentTime()}: Label and Meta data was updated successfully (image id: '{imageId}').")
        else:
            logging.warn(
                    "{}: Update label (image id: '{}') failed due to response code = {}) ".format(
                        self.getCurrentTime(), imageId, response.status_code
                    )
                )

        return response.status_code

    def deleteLabelByVersionTag(self, imageId : str, versionTag : str) -> int:
        url = "http://localhost:8000/datastore/label?id={}&tag={}".format(imageId, versionTag)
        response = requests.delete(url)
        if(response.status_code == 200):
            logging.info(f"{self.getCurrentTime()}: Label and Meta data was deleted successfully (image id: '{imageId}') | tae: '{versionTag}'.")
        else:
             logging.warn(
                    "{}: Deletion of label (image id: '{}') failed due to response code = {}) ".format(
                        self.getCurrentTime(), imageId, response.status_code
                    )
                )
        return response.status_code
