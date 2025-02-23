from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import SimpleITK as sitk
import os
import numpy as np
import pandas as pd
import scipy.ndimage
import time
import os
import cv2
from skimage.measure import regionprops
from shutil import copyfile
import tensorflow as tf
import pydicom as dicom
import sys

# Custom Model Data Generator for Non-Serial Data
#data_xlsx = '/content/drive/MyDrive/MasterThesis/ProstateMR_USSL/Datasets/metadata.xlsx'
def custom_data_generator(data_xlsx, train_obj='zonal', probabilistic=False, test=False):
    """
    Custom Generator that uses Paths to Image + Labels (via XLSX) to 
    Load Data of Size [depth,height,width,#channels] and Sequentially Yield the Same.

    Note: 
    1)  Takes Preprocessed NumPy Data as Input.
    2)  Compatible with tf.data.Dataset Wrappers for Python Generators.
    """
    # Load I/O Datasheet + Initialize Arrays
    all_data   = pd.read_excel(data_xlsx) #data_xlsx = TRAIN_XLSX
    
    i = 0
    while True:
        # Restart Counter
        if ((i+1)>len(all_data['image_path'])):  i = 0 

        # Prepare Model I/O
        while True: # To Counter {BlockingIOError: Resource temporarily unavailable}
            try:
                
                # Anatomical Segmentation (WG,TZ,PZ)
                if (train_obj=='zonal'):
                    image  = dicom.dcmread(all_data['image_path'][i])
                    if image.ndim == 4: image = image[:,:,:,:1]
                    # image  = image[..., np.newaxis]   
                    if not test:
                        zones  = dicom.dcmread(all_data['zones_path'][i]).astype(np.uint8)
                        tz, pz = zones.copy() , zones.copy()  
                        tz[zones!=1], pz[zones!=2] = 0,0 
                        tz[zones==1], pz[zones==2] = 1,1                                       # Binarize TZ/PZ Annotations Independently
                        tz, pz = contour_smoothening(tz), contour_smoothening(pz)              # Smoothen Contour Definitions
                        label  = np.stack([np.ones_like(zones)-tz-pz, tz, pz], axis=-1)        # One-Hot Encoding
                    else:
                        label  = np.stack([np.zeros_like(image[...,0]), np.zeros_like(image[...,0]), np.zeros_like(image[...,0])], axis=-1)
                # Diagnostic Segmentation (csPCa)
                if (train_obj=='lesion'):
                    image   = dicom.dcmread(all_data['image_path'][i]).pixel_array   
                    lesions = dicom.dcmread(all_data['label_path'][i]).pixel_array
                    #print(lesions.dtype)
                    #lesions[lesions<=1] = 0                         
                    #lesions[lesions>=2] = 1                                                # Binarize Annotation (csPCa: GGG>=2)
                    lesions = contour_smoothening(lesions)                                 # Smoothen Contour Definitions
                    label   = np.stack([np.ones_like(lesions)-lesions, lesions], axis=-1)  # One-Hot Encoding
                break
            except Exception as e: 
                print(e)
                continue
        i += 1

        # Bayesian/Probabilistic Segmentation
        if probabilistic:          
            yield {"image":     np.concatenate((image.copy(),label.copy()[:,:,:,1:].copy()), axis=-1)},{
                   "detection": label.copy(),
                   "KL":        np.zeros(shape=label.shape)}
        # Standard/Deterministic Segmentation
        else:
            yield {"image":     image.copy()},{
                   "detection": label.copy()},{
                   "Dimention": image.ndim}
  #print(data_xlsx)

# Smoothen Annotation Contours Post-Resampling
def contour_smoothening(label, kernel_2d=(7,7), iterations=1):
    for _ in range(iterations):
        for k in range(label.shape[0]):
            label[k] = cv2.GaussianBlur(label[k].copy().astype(np.uint8), 
                                        kernel_2d, cv2.BORDER_DEFAULT)
    return label
