from pdf2image import convert_from_path
import os
from .slip import split_columns_and_rows
import shutil
import platform

def ensure_directories():
    """
    确保所需的目录存在
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建必要的目录
    dirs_to_create = [
        os.path.join(current_dir, "read"),
        os.path.join(current_dir, "temp_images")
    ]
    
    for directory in dirs_to_create:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"创建目录: {directory}")

def check_poppler():
    """
    检查 poppler 是否正确安装
    """
    system = platform.system().lower()
    
    if system == "windows":
        # 直接设置 poppler 路径
        poppler_path = r'E:\poppler\poppler-24.08.0\Library\bin'
        if not os.path.exists(poppler_path):
            print("错误：未找到 poppler")
            print(f"请确认路径是否正确: {poppler_path}")
            print("或者按照以下步骤安装 poppler：")
            print("1. 下载 poppler：https://github.com/oschwartz10612/poppler-windows/releases/")
            print("2. 解压下载的文件")
            print("3. 将解压后的 bin 目录添加到系统环境变量 PATH 中")
            print("4. 或者修改代码中的 poppler_path 变量为正确的路径")
            return False, None
        return True, poppler_path
    elif system == "linux":
        if os.system("which pdftoppm > /dev/null 2>&1") != 0:
            print("错误：未找到 poppler-utils")
            print("请运行以下命令安装：")
            print("sudo apt-get install poppler-utils")
            return False, None
    elif system == "darwin":  # macOS
        if os.system("which pdftoppm > /dev/null 2>&1") != 0:
            print("错误：未找到 poppler")
            print("请运行以下命令安装：")
            print("brew install poppler")
            return False, None
    
    return True, None

def process_pdf(pdf_path, out_input, output_dir="temp_images"):
    """
    处理PDF文件：
    1. 检查环境
    2. 将PDF转换为图片
    3. 对每个图片进行OCR识别
    4. 分析识别结果
    """
    # 确保必要的目录存在
    ensure_directories()
    
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 检查 poppler 是否安装
    poppler_check, poppler_path = check_poppler()
    if not poppler_check:
        return 0

    # 检查输入文件是否存在
    if not os.path.exists(pdf_path):
        print(f"错误：文件 {pdf_path} 不存在")
        return 0
    
    # 使用绝对路径创建临时目录
    output_dir = os.path.join(current_dir, output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    try:
        # 将PDF转换为图片
        print("正在将PDF转换为图片...")
        # 对于 Windows 系统，显式设置 poppler_path
        if platform.system().lower() == "windows":
            print(f"使用 poppler 路径: {poppler_path}")
            images = convert_from_path(pdf_path, poppler_path=poppler_path)
        else:
            images = convert_from_path(pdf_path)
        
        # 使用绝对路径处理ocr_results.txt
        ocr_results_path = os.path.join(current_dir, "read", "oocr_results.txt")
        os.makedirs(os.path.dirname(ocr_results_path), exist_ok=True)
        
        # 清空ocr_results.txt文件
        with open(ocr_results_path, "w", encoding="utf-8") as f:
            f.write("")
        
        # 处理每一页
        for i, image in enumerate(images):
            # 保存图片
            image_path = os.path.join(output_dir, f'page_{i+1}.png')
            image.save(image_path, 'PNG')
            
            print(f"正在处理第 {i+1} 页...")
            # 对图片进行分割和OCR识别
            split_columns_and_rows(image_path, out_input)
            
            # 删除临时图片
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # 分析OCR结果
        print("正在分析识别结果...")

        return 1

    except Exception as e:
        print(f"处理PDF时发生错误: {str(e)}")
        print(f"错误类型: {type(e)}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")
        return 0
    finally:
        # 清理临时目录
        if os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
            except Exception as e:
                print(f"清理临时目录时发生错误: {str(e)}")