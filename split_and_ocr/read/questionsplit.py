from split_and_ocr.ai import aiapi
from split_and_ocr.ai import new
import re
import os

def oreadexit():
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ocr_file = os.path.join(current_dir, "oocr_results.txt")

    with open(ocr_file, "r", encoding="utf-8") as f:
        Otxt = f.read()
    f.close()
    print(Otxt)
    line1 = f"{Otxt}"
    line2 = "上述是试卷题目，请对题目进行整理，输出原试卷，不进行补充答案但补充题目只输出题目，识别到的其他题目也去除,大题和大题之间用----分割,强调只分割大题，不分割小题，同类题型，例如选择题和选择题不分割，填空题和填空题不分割，例如：请简述本章介绍的 4 种 Exception 类异常并说明其产生的原因。\n----\n五、编程题"
    admittxt = new(line1, line2)
    print(admittxt)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for i in admittxt.split("----"):
        # 去除空白行
        i = i.strip()
        if not i:
            continue

        # 获取所有行
        lines = i.split('\n')

        # 过滤掉空行
        lines = [line.strip() for line in lines if line.strip()]

        if not lines:
            continue

        # 使用第一行作为文件名
        filename = lines[0].strip()
        if filename:
            # 去除文件名中的非法字符
            filename = re.sub(r'[\\/:*?"<>|]', '', filename)
            # 将所有题目写入以大题标题命名的文件
            output_file = os.path.join(current_dir, f"o{filename}.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

def readexit():
    # 获取当前文件所在目录的上两级目录（split_and_ocr目录）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ocr_file = os.path.join(base_dir, "ocr_results.txt")
    
    with open(ocr_file, "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    line = f"{Otxt}是试卷题目，请对题目进行整理，输出原试卷，不进行补充答案但补充题目只输出题目，识别到的其他题目也去除,大题和大题之间用----分割,只分割大题"
    admittxt = aiapi(line)
    print(admittxt)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for i in admittxt.split("----"):
        # 去除空白行
        i = i.strip()
        if not i:
            continue
            
        # 获取所有行
        lines = i.split('\n')
        
        # 过滤掉空行
        lines = [line.strip() for line in lines if line.strip()]
        
        if not lines:
            continue
            
        # 使用第一行作为文件名
        filename = lines[0].strip()
        if filename:
            # 去除文件名中的非法字符
            filename = re.sub(r'[\\/:*?"<>|]', '', filename)
            # 将所有题目写入以大题标题命名的文件
            output_file = os.path.join(current_dir, f"{filename}.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

if __name__ == '__main__':
    oreadexit()