import cv2
import numpy as np
from skimage import filters, io, color
from .Chart import bar_chart
import matplotlib.pyplot as plt

# 得到图片的灰度值
def get_gray_value(img):
    # 把图片转换为灰度图
    gray_img = img.convert('L')
    width, height = img.size
    img_array = numpy.array(gray_img)  # 转换为数组
    average = numpy.mean(img_array)  # 计算平均亮度 返回
    count = numpy.bincount(numpy.ravel(img_array), minlength=255)  # 统计某个元素出现的个数，记录 count[1] : 2 表示1出现了两次

    word_gray = width * height * 0.08
    all = 0
    bar_chart(range(0, 255), count[0:255])

    for i in range(0, 255):
        all = all + count[i]
        if all > word_gray:
            return i

def skimage_gray_value(img_path):
    sk_img = io.imread(img_path)
    if sk_img.shape[-1] == 4:  # 如果图片有 4 通道，去掉 Alpha 通道
        sk_img = sk_img[:, :, :3]
    img = color.rgb2gray(sk_img)  # 获取灰度图片

    thresh = filters.threshold_otsu(img)  # 计算二值化阈值
    return thresh * 256
