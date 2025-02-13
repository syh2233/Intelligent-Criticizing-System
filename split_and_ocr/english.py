from PIL import Image, ImageEnhance
import os
import re
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

def can_split_center(img):
    """判断图片正中间是否可以进行列分割"""
    center_x = img.size[0] // 2
    middle_strip = img.crop((center_x - 10, 0, center_x + 10, img.size[1]))
    non_white_pixels = sum(1 for pixel in middle_strip.getdata() if sum(pixel[:3]) < 600)  # 阈值调整
    print(f"中间区域非白色像素数量: {non_white_pixels}, 图片高度的一半: {0.5 * middle_strip.size[1]}")
    return non_white_pixels < (0.5 * middle_strip.size[1])  # 宽松判断

def split_by_sections(img_path, section_coords, output_dir="output_sections", prefix="section"):
    """根据检测到的 Section 标题区域分割图片，并保留分割外的部分"""
    img = Image.open(img_path)
    width, height = img.size

    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 分割图片
    prev_bottom = 0
    for i in range(len(section_coords)):
        top = section_coords[i][0]  # 当前 Section 的顶部
        if i + 1 < len(section_coords):
            bottom = section_coords[i + 1][0]  # 下一 Section 的顶部
        else:
            bottom = height  # 最后一个 Section 到底部

        # 保存分割部分
        section_img = img.crop((0, max(prev_bottom, int(top)), width, min(height, int(bottom))))
        section_path = os.path.join(output_dir, f"{prefix}_{i + 1}.png")
        section_img.save(section_path)
        print(f"保存 Section 图片: {section_path}")

        # 保存分割外的部分
        if prev_bottom < top:
            outside_img = img.crop((0, prev_bottom, width, top))
            outside_path = os.path.join(output_dir, f"{prefix}_outside_{i + 1}.png")
            outside_img.save(outside_path)
            print(f"保存分割外图片: {outside_path}")

        prev_bottom = bottom  # 更新上一个分割的底部

def detect_section_regions(img_path):
    """检测图片中所有以 'Section' 或 'Passage' 开头的段落位置"""
    img = enhance_image(Image.open(img_path))
    ocr_result = ocr.ocr(img_path, cls=True)
    section_prefix_pattern = re.compile(r"^(Passage|Section)\b", re.IGNORECASE)

    section_coords = []
    for line in ocr_result[0]:
        text, bbox = line[1][0], line[0]
        if section_prefix_pattern.match(text.strip()):
            section_coords.append((bbox[0][1] - 10, bbox[2][1] + 10))  # 获取顶部和底部 Y 坐标

    # 根据 Y 坐标排序，确保从上到下顺序
    section_coords = sorted(section_coords, key=lambda x: x[0])
    return section_coords

def enhance_image(img):
    """增强图片清晰度和对比度"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.5)  # 提高清晰度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)  # 提高对比度
    return img

def concatenate_images_vertically(img1_path, img2_path, output_path):
    """将两张图片以垂直方式拼接，img1 在上，img2 在下。"""
    img1 = Image.open(img1_path)
    img2 = Image.open(img2_path)

    # 计算拼接后图片的尺寸
    width = max(img1.width, img2.width)
    total_height = img1.height + img2.height

    # 创建空白图像
    concatenated_image = Image.new("RGB", (width, total_height))

    # 粘贴图像
    concatenated_image.paste(img1, (0, 0))
    concatenated_image.paste(img2, (0, img1.height))

    # 保存拼接后的图像
    concatenated_image.save(output_path)
    print(f"拼接完成并保存到: {output_path}")

def split_columns_and_sections_with_merge(img_path, output_dir="output_split"):
    """进行列分割，并将左列最后一部分与右列第一部分拼接"""
    img = enhance_image(Image.open(img_path))
    width, height = img.size

    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if can_split_center(img):
        # 列分割
        left_img = img.crop((0, 0, width // 2, height))
        right_img = img.crop((width // 2, 0, width, height))

        # 保存列分割图片
        left_path = os.path.join(output_dir, "column_left.png")
        right_path = os.path.join(output_dir, "column_right.png")
        left_img.save(left_path)
        right_img.save(right_path)
        print(f"列分割完成，保存图片：{left_path} 和 {right_path}")

        # 分别检测和分割每列的 Section
        left_section_coords = detect_section_regions(left_path)
        right_section_coords = detect_section_regions(right_path)
        split_by_sections(left_path, left_section_coords, os.path.join(output_dir, "left_sections"), prefix="left_section")
        split_by_sections(right_path, right_section_coords, os.path.join(output_dir, "right_sections"), prefix="right_section")

        # 拼接左列最后一部分与右列第一部分
        last_left_section = os.path.join(output_dir, "left_sections", "left_section_2.png")  # 替换为左列最后部分路径
        first_right_outside = os.path.join(output_dir, "right_sections", "right_section_outside_1.png")  # 替换为右列第一部分路径
        concatenated_output = os.path.join(output_dir, "concatenated_image.png")
        concatenate_images_vertically(last_left_section, first_right_outside, concatenated_output)
    else:
        # 如果不能列分割，则直接进行 Section 分割
        section_coords = detect_section_regions(img_path)
        split_by_sections(img_path, section_coords, output_dir)

if __name__ == "__main__":
    # 输入图片路径
    img_path = "../分割算法+ocr+阅卷/image/IMG_20250115_000736.jpg"  # 替换为您的图片路径
    split_columns_and_sections_with_merge(img_path)
