import logging
import datetime
from typing import Dict, List
from ReviewerLibs.ImageData import ImageData
from ReviewerLibs.MONAILabelReviewerEnum import Level

'''
ImageDataExtractor gets dictionary (mapping from id to ImageData from JsonParser) and caches 
    Mapping:
        - imageIds TO ImageData,  
        - client TO list of imageIds
    List:
        - imageIds of all images which are not segemented yet
        - imageIds of all images which are approved
        - all reviewers

Each modification during review process will be stored in corresponding ImageData
ImageDataExtractor provides the meta data across all ImageData-Containers when the user selects the filter option
'''

class ImageDataExtractor:
    def __init__(self, nameToImageData : dict):
        self.LEVEL = Level()
        self.nameToImageData : Dict[str, ImageData] = nameToImageData

        self.clientToImageIds : Dict[str, list]= {}
        self.idsOfNotSegmented : List[str] = []
        self.idsOfApprovedSementations : List[str] = []
        self.reviewers : List[str] = []
       
    def init(self):
        self.groupImageDataByClientId()
        self.extractAllReviewers()
        self.extractNotSegmentedImageIds()

    def getCurrentTime(self)->datetime:
        return datetime.datetime.now()

    def groupImageDataByClientId(self):
        for imageId, imageData in self.nameToImageData.items():
            if(imageData.isSegemented()):
               
                clientId = imageData.getClientId()
                if clientId:
                    if (clientId not in self.clientToImageIds):
                        self.clientToImageIds[clientId] = []
                    self.clientToImageIds[clientId].append(imageId)

    def extractAllReviewers(self):
        for imageId, imageData in self.nameToImageData.items():
            if(imageData.isSegemented()):
                reviewer = imageData.getApprovedBy()
                if(reviewer not in self.reviewers and reviewer != ""):
                    self.reviewers.append(reviewer)

    def extractNotSegmentedImageIds(self):
        for imageId, imageData in self.nameToImageData.items():
            if(imageData.isSegemented() == False):
                self.idsOfNotSegmented.append(imageId)

    def getTotalNumImages(self) -> int: 
        return len(self.nameToImageData)

    def getImageDataIds(self) -> List[str]:
        return [*self.nameToImageData.keys()]

    def getClientIds(self) -> List[str]:
        return [*self.clientToImageIds.keys()]

    def getReviewers(self) -> List[str]:
        return self.reviewers

    def getImageDataNotsegmented(self) -> List[ImageData]:
        '''
        returns list of ImageData of corresponingd image studies wich has not been segemeted
        '''
        notSegmented = []
        for id in self.idsOfNotSegmented:
            imageData = self.nameToImageData[id]
            notSegmented.append(imageData)
        return notSegmented

    def getNumOfNotSegmented(self) -> int:
        return len(self.idsOfNotSegmented)

    def getNumOfSegmented(self) -> int:
        count = 0
        for client, idList in self.clientToImageIds.items():
            count += len(idList)
        return count

    def getSegmentationProgessInPercentage(self) -> int:
        '''
        returns percentage of already segmented images out of all available images
        '''
        segmentedCount = self.getNumOfSegmented()
        float_Num = segmentedCount / self.getTotalNumImages()
        return int(float_Num * 100)

    def getSegmentationVsTotalStr(self) -> str:
        '''
        returns the index of subjected imageData within imageData data set
        '''
        segmentedCount = self.getNumOfSegmented()
        idxTotalSegmented : str = "{}/{}".format(segmentedCount, self.getTotalNumImages())
        return idxTotalSegmented

    def getApprovalProgressInPercentage(self) -> int:
        '''
        returns percentage of already approved imageData out of all available imageData
        '''
        approvalCount = self.getNumApprovedSegmentation()
        fraction = approvalCount / self.getTotalNumImages()
        return int(fraction * 100)

    def getApprovalVsTotal(self) -> str:
        approvalCount = self.getNumApprovedSegmentation()
        idxTotalApproved : str = "{}/{}".format(approvalCount, self.getTotalNumImages())
        return idxTotalApproved


    def getAllImageData(self, segmented=False, notSegmented=False, approved=False, flagged=False) -> List[ImageData]:
        '''
        returns fitered list of imageData which are filtered according to input parameters
        '''
        if((notSegmented and segmented) 
            or (approved and flagged)
            or (notSegmented and approved)
            or (notSegmented and flagged)):
            logging.warning("{}: Selected filter options are not valid: segmented='{}' | notSegmented='{}' | approved='{}' | flagged='{}')".format(self.getCurrentTime(), segmented, notSegmented, approved, flagged))
            return None

        if(notSegmented==False
            and segmented==False
            and approved==False
            and flagged==False):
            return [*self.nameToImageData.values()]
        
        selectedImageData = []
        for imagedata in self.nameToImageData.values():

            if(notSegmented==True and segmented==False and imagedata.isSegemented()==False):
                selectedImageData.append(imagedata)
                continue

            if(segmented==imagedata.isSegemented() and approved==imagedata.isApproved() and flagged==imagedata.isFlagged()):
                selectedImageData.append(imagedata)
                continue
        
        return selectedImageData

    def getImageDataByClientId(self, clientId : str, approved=False, flagged=False) -> List[ImageData]:
        '''
        returns fitered list of imageData which are filtered according to client (=annotator) and parameters (approved, flagged)
        '''
        
        if(clientId == ""):
            return None
        if(approved and flagged):
            logging.warning("{}: Selected filter options are not valid: approved='{}' and flagged='{}')".format(self.getCurrentTime(), approved, flagged))
            return None

        imageIds = self.clientToImageIds[clientId]
        imageDataList = []
        for id in imageIds:
            if(id not in self.nameToImageData):
                logging.error("{}: Image data [id = {}] not found for [clientId = {}] ".format(self.getCurrentTime(), id, clientId))
                continue
            imageData = self.nameToImageData[id]
            if(approved and imageData.isApproved()==False):
                continue
            if(flagged and imageData.isFlagged()==False):
                continue

            imageDataList.append(imageData)
        return imageDataList

    def getImageDataByClientAndReviewer(self, clientId : str, reviewerId : str, approved=False, flagged=False)-> List[ImageData]:
        '''
        returns fitered list of imageData which are filtered according to client (=annotator) and reviewer and parameters (approved, flagged)
        '''
        
        imageDatas = self.getImageDataByClientId(clientId, approved, flagged)
        filteredByRewiewer = list(filter(lambda imageData: (imageData.getApprovedBy() == reviewerId), imageDatas))
        return filteredByRewiewer
    
    def getImageDataByReviewer(self, reviewerId : str, approved=False, flagged=False) -> List[ImageData]:
        if(reviewerId == ""):
            return None
        if(approved and flagged):
            logging.warning("{}: Selected filter options are not valid: approved='{}' and flagged='{}')".format(self.getCurrentTime(), approved, flagged))
            return None
        
        filteredImageDataList = []

        for imageData in self.nameToImageData.values():
            if(imageData.isSegemented()==False):
                continue
            if(approved and imageData.isApproved()==False):
                continue
            if(flagged and imageData.isFlagged()==False):
                continue
            if(imageData.getApprovedBy()==reviewerId):
                filteredImageDataList.append(imageData)
            
        return filteredImageDataList

    def getImageDataByLevel(self, isEasy : bool, isMedium : bool, isHard : bool) -> Dict[str, ImageData]:
        '''
        returns fitered list of imageData which are filtered according to level of difficulty (regarding segmentation): easy, medium, hard
        '''
        filteredImageData = {}
        for id, imagedata in self.nameToImageData.items():
            if(imagedata == None):
                continue
            if(imagedata.isSegemented == "False"):
                continue
            if(isEasy and imagedata.getLevel()==self.LEVEL.EASY):
                filteredImageData[id] = imagedata
                continue

            if(isMedium and imagedata.getLevel()==self.LEVEL.MEDIUM):
                filteredImageData[id] = imagedata
                continue

            if(isHard and imagedata.getLevel()==self.LEVEL.HARD):
                filteredImageData[id] = imagedata
        return filteredImageData


    def getSingleImageDataById(self, imageId : str) -> ImageData:
        '''
        returns imageData by given imageId
        '''
        if(self.isBlank(imageId)):
            return None
        if(imageId not in self.nameToImageData):
            logging.warning("{}: Image data for requested id [{}] not found".format(self.getCurrentTime(), imageId))
            return None
        return self.nameToImageData[imageId]

    def getMultImageDataByIds(self, ids : List[str]) -> Dict[str, ImageData]:
        '''
        returns multiple imageData by given list of imageId
        '''
        idToimageData : Dict[str, ImageData]= {}
        if(len(ids) == 0):
            logging.warning("{}: Given id list is empty.".format(self.getCurrentTime()))
            return idToimageData
        for id in ids:
            imageData = self.getSingleImageDataById(id)
            if(imageData == None):
                continue
            idToimageData[imageData.getName()] = imageData
        return idToimageData

    def getNumApprovedSegmentation(self) -> int:
        '''
        returns total number of imageData which are approved
        '''
        count = self.countApprovedSegmentation(self.nameToImageData.values())
        return count

    def countApprovedSegmentation(self, imageDatas : List[ImageData]) -> int:
        if (imageDatas == None):
            return 0
        approvedCount = 0
        for imageData in imageDatas:
            if(imageData == None):
                continue
            if(imageData.isApproved()):
                 approvedCount += 1
        return approvedCount

    def getPercentageApproved(self, clientId : str):
        '''
        returns the percentage of images that have already been approved by given client (=Annotator)
        and the value: (total number of images approved by given client (=Annotator))/(total number of imageData)
        '''
        listImageData = self.getImageDataByClientId(clientId=clientId)
        approvedCount = self.countApprovedSegmentation(listImageData)
        if(len(listImageData) == 0):
            logging.warning("{}: There are no images".format(self.getCurrentTime()))
            return 0
        fraction = approvedCount / len(listImageData)
        precentage = int(fraction * 100)
        idxApprovedOfClient : str = "{}/{}".format(approvedCount, len(listImageData))
        return precentage, idxApprovedOfClient

    def getPercentageSemgmentedByClient(self, clientId : str):
        '''
        returns the percentage of images that have already been segmented by given client (=Annotator)
        and the value: (total number of images segmented by given client (=Annotator))/(total number of imageData)
        '''
        numSegementedByClient = len(self.clientToImageIds[clientId])
        fraction = numSegementedByClient / self.getTotalNumImages()
        precentage = int(fraction * 100)
        idxSegmentedByClient : str = "{}/{}".format(numSegementedByClient, self.getTotalNumImages())
        return precentage, idxSegmentedByClient

    def getApprovedSegmentationIds(self) -> List[str]:
        '''
        returns list of ids of all approved imageData
        '''
        idsOfApprovedSementations = []
        for imageId, imageData in self.nameToImageData.items():
             if(imageData.isApproved()):
                idsOfApprovedSementations.append(imageId)
        return idsOfApprovedSementations

    def getSegmentedImageIds(self) -> List[str]:
        '''
        returns list of ids of all segmented imageData
        '''
        idsOfSegmented = []
        for imageId, imageData in self.nameToImageData.items():
             if(imageData.isSegemented()):
                 idsOfSegmented.append(imageId)
        return idsOfSegmented

    def isBlank(self, string) -> bool:
        return not (string and string.strip())
