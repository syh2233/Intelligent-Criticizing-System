from PIL import Image, ImageEnhance
import cv2
import numpy as np
from paddleocr import PaddleOCR

# 初始化 PaddleOCR
ocr = PaddleOCR(
    use_angle_cls=True,
    lang='ch',
    det_model_dir="D:/.paddleocr/whl/det/ch_PP-OCRv4_det_infer",
    rec_model_dir="D:/.paddleocr/whl/rec/ch_PP-OCRv4_rec_infer",
    cls_model_dir="D:/.paddleocr/whl/cls/ch_ppocr_mobile_v2.0_cls_infer",
    show_log=False
)

# 增强图片质量
def enhance_image(img):
    # 将图片转换为 RGB 模式
    if img.mode != 'RGB':
        img = img.convert('RGB')
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)  # 提高清晰度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)  # 提高对比度
    return img

def zi_file(image_path):
    """
    使用 PaddleOCR 识别本地图片中的文字
    """
    try:
        pil_img = Image.open(image_path)
        # 修复图片模式问题并增强处理
        pil_img = enhance_image(pil_img)
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)  # 转换为 OpenCV 格式
        result = ocr.ocr(img_cv, cls=True)
        wen = ""
        for line in result[0]:
            wen += line[1][0] + "\n"
        return wen
    except Exception as e:
        print(f"图片文字识别失败: {e}")
        return "图片文字识别失败"

def zi_pil(img):
    """
    使用 PaddleOCR 识别 PIL 格式的图片文字
    :param img: PIL.Image 图片对象
    :return: str 识别出的文字
    """
    try:
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        result = ocr.ocr(img_cv, cls=True)
        wen = ""
        for line in result[0]:
            wen += line[1][0] + "\n"
        return wen
    except Exception as e:
        print(f"图片文字识别失败: {e}")
        return "图片文字识别失败"

if __name__ == '__main__':
    # 示例：本地图片路径
    path = "../分割算法+ocr+阅卷/image/微信图片_20250125125634.png"
    print("使用文件路径识别:")
    print(zi_file(path).replace("\n",""))

    # 示例：PIL 图片对象
    print("使用 PIL 图像对象识别:")
    img = Image.open(path)
    print(zi_pil(img))
