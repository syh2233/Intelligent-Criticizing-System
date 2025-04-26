import cv2
import numpy as np
from paddleocr import PaddleOCR
import os
import matplotlib.pyplot as plt
import time
from PIL import Image
from .Calculate import skimage_gray_value
from .Chart import bar_chart
from .myocr import zi_file, zi_pil

# 初始化OCR
ocr = PaddleOCR(
    use_angle_cls=True,
    lang='ch',
    det_model_dir="D:/.paddleocr/whl/det/ch_PP-OCRv4_det_infer",
    rec_model_dir="D:/.paddleocr/whl/rec/ch_PP-OCRv4_rec_infer",
    cls_model_dir="D:/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer",
    show_log=False
)



def can_split_center(img):
    """
    判断图片正中间是否可以进行列分割
    """
    try:
        ocr_result = ocr.ocr(np.array(img), cls=True)
        if not ocr_result or not ocr_result[0]:  # 检查OCR结果是否为空
            print("OCR未识别到文字，默认不进行分割")
            return False
            
        center_x = img.size[0] // 2
        left_text, right_text = False, False

        for line in ocr_result[0]:
            bbox = line[0]
            left, right = bbox[0][0], bbox[2][0]
            if left < center_x and right < center_x:
                left_text = True  # 左半部分有文字
            elif left > center_x and right > center_x:
                right_text = True  # 右半部分有文字

        # 如果左右两部分都有文字，则可以分割
        return left_text and right_text
    except Exception as e:
        print(f"分割判断时发生错误: {str(e)}")
        return False  # 发生错误时默认不分割

debug = False

# 列分割
def AcrCut(img):
    li = list(np.sum(np.array(img) == 0, axis=0))  # 对每一列进行求和并返回一行元素
    img_array = np.array(img)  # 将img转数组
    posx = []
    for i in range(3, len(li) - 3):
        if i > 0 and li[i] <= 3 and li[i - 3] <= 3 and li[i + 3] <= 3:  # 判断当前列有没有内容
            posx.append(i)
    width, height = img.size
    cutx = []
    i = 0
    while i < len(posx):
        t = i
        while i < len(posx) - 1 and posx[i + 1] < posx[i] + 5:  # 判断相邻的是否为黑色
            i = i + 1
        if i - t > 10:  # 相邻为黑色的超过10个像素，则可以切
            cutx.append(int((posx[t] + posx[i]) / 2))
        i = i + 1
    if debug:
        ''' ----- 显示 调试部分 ----  '''
        for i in range(len(cutx)):
            for j in range(height):
                img_array[j][cutx[i]] = 0  # 全部赋值为1
        img_array = np.uint8(img_array)  # 转类型
        img_array[img_array > 0] = 255  # 将1转为255
        Image.fromarray(img_array).show()  # 返回图片
    print(cutx)
    return cutx

# 行切割标准
def HorCutCheck(i, prei, dis=5):
    return i > prei + dis  # 忽略相邻三个像素的点内有分割线

# 计算切割信息
def HorCutDate(cuty, cutt, cutb):
    disy = []
    for i in range(1, len(cuty)):
        disy.append(cuty[i] - cuty[i - 1])


    median = np.median(disy)  # 中值
    median = int(median) >> 1
    tempcuty = []
    tempcutt = []
    tempcutb = []
    for i in range(0, len(disy)):
        if median > disy[i]:  # 去除过小的分割
            # print(str(cuty[i]) + " " + str(disy[i]))
            continue
        else:
            tempcuty.append(cuty[i])
            tempcutt.append(cutt[i])
            tempcutb.append(cutb[i])

    tempcuty.append(cuty[len(cuty) - 1])
    cuty = tempcuty

    disy = []
    for i in range(1, len(cuty)):
        disy.append(cuty[i] - cuty[i - 1])

    return tempcutt, cuty, tempcutb, disy

# 行分割
def HorCut(img  # PIL格式
           , yuzhi=0  # 阈值 行和大于该值时不可分割(默认为 width*0.007+1)
           ):
    width, height = img.size
    img_array = np.array(img)  # 将img转数组
    if yuzhi == 0:
        yuzhi = width * 0.005 + 1

    li = list(np.sum(img_array == 0, axis=1))  # 将其转换为array并求和
    k = 1
    posy = [0]
    cuty = []
    cutt = [0]  # 空白区域的top
    cutb = []  # 空白区域的bottom
    for i in range(1, len(li)):
        if li[i] <= yuzhi:
            if HorCutCheck(i, posy[k - 1]):
                # img_array[i] = np.zeros(width, dtype=bool)  # 全部赋值为1
                cutt.append(i)
                cutb.append(posy[k - 1])
            posy.append(i)
            k = k + 1

    cutb.append(height)
    for i in range(len(cutt)):
        cuty.append(int((cutt[i] + cutb[i]) / 2))  # 记录切点位置 空白区域中间部分

    cutt, cuty, cutb, disy = HorCutDate(cuty, cutt, cutb)
    ''' ----- 显示 调试部分 ----  '''
    if debug:
        bar_chart(range(0, len(disy)), disy)  # 图表
        for i in range(len(cuty)):
            img_array[cuty[i]] = np.zeros(width, dtype=bool)  # 全部赋值为1
        img_array = np.uint8(img_array)  # 转类型
        img_array[img_array > 0] = 255  # 将1转为255
        Image.fromarray(img_array).show()  # 返回图片

    return {"cuty": cuty, "disy": disy, "posy": posy, "cutt": cutt, "cutb": cutb}

# 图像二值化
def binarize(img, threshold=120):
    img = img.convert('L')

    table = []
    for i in range(256):
        if i > threshold:
            table.append(1)
        else:
            table.append(0)
    bin_img = img.point(table, '1')  # 根据table表进行区分

    return bin_img

def pre_run(img_input, out_input):
    """
    处理输入的图像
    :param img_input: 可以是图片路径字符串或PIL Image对象
    """
    if isinstance(img_input, str):
        img = Image.open(img_input)
    else:
        img = img_input  # 如果已经是PIL Image对象，直接使用
    
    if debug:
        img.show()
    
    # 如果是路径，使用skimage处理
    if isinstance(img_input, str):
        gray_value = skimage_gray_value(img_input)
    else:
        # 如果是PIL Image对象，先保存为临时文件
        temp_path = "temp_image_for_skimage.png"
        img.save(temp_path)
        gray_value = skimage_gray_value(temp_path)
        os.remove(temp_path)  # 删除临时文件
    
    print("end skimage_gray_value time:" + str(time.time()))
    re_img = binarize(img, gray_value)  # 二值化
    if debug:
        re_img.show()
    data = AcrCut(re_img)  # 列切割
    if debug:
        data = HorCut(re_img)  # 行切割，将图片中文字分行

    print("end HorCut time:" + str(time.time()))
    # OCR 替换为 PaddleOCR 识别
    if isinstance(img_input, str):
        ocr_result = zi_file(img_input)
    else:
        ocr_result = zi_pil(img)

    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    read_dir = os.path.join(current_dir, "read")
    
    # 确保read目录存在
    os.makedirs(read_dir, exist_ok=True)
    
    # 使用绝对路径创建和写入文件
    results_file = os.path.join(read_dir, out_input)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(ocr_result)
        print(f"OCR 结果已保存到 {results_file}")
    
    return data

def split_columns_and_rows(img_input, out_input):
    """
    先进行列分割，然后对每列图片进行行分割
    :param img_input: 可以是图片路径字符串或PIL Image对象
    """
    try:
        # 打开原图
        if isinstance(img_input, str):
            img = Image.open(img_input)
        else:
            img = img_input
        width, height = img.size

        if can_split_center(img):
            # 列分割，将图片左右分为两半
            left_img = img.crop((0, 0, width // 2, height))
            right_img = img.crop((width // 2, 0, width, height))

            print("列分割完成，直接进行 OCR 分析")

            # 调用 pre_run 函数处理分割后的图像
            print("处理左图：")
            pre_run(left_img, out_input)

            print("处理右图：")
            pre_run(right_img, out_input)

            print("列分割处理完成")
        else:
            print("无法进行列分割，进行整页处理")
            pre_run(img, out_input)
    except Exception as e:
        print(f"分割处理时发生错误: {str(e)}")
        # 如果发生错误，尝试直接处理整个图像
        try:
            print("尝试直接处理整个图像...")
            pre_run(img_input, out_input)
        except Exception as e2:
            print(f"处理整个图像时也发生错误: {str(e2)}")
            raise  # 如果连直接处理也失败，则抛出异常

if __name__ == "__main__":
    # 输入图片路径
    img_path = "../分割算法+ocr+阅卷/image/b6ce94d7-0e16-4764-a1e9-d5ce0198294f.png"
    out_input= "ocr_results.txt"
    split_columns_and_rows(img_path, out_input)

