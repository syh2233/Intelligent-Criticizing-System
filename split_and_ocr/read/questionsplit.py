import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from split_and_ocr.ai import new
import re
import os


def find_ocr_file(directory, base_name=None):
    """
    在指定目录中查找OCR结果文件，支持多种可能的文件名格式

    参数:
    directory: 查找目录
    base_name: 基本文件名（如果提供）

    返回:
    找到的文件路径，如果未找到则返回None
    """
    # 首先检查是否存在指定名称的文件
    if base_name:
        specific_file = os.path.join(directory, base_name)
        if os.path.exists(specific_file):
            print(f"找到指定的OCR结果文件: {specific_file}")
            return specific_file

    # 可能的文件名前缀和基本名称
    prefixes = ["", "@", "o", "O", "_"]
    base_names = ["ocr_results.txt", "ocr_result.txt"]

    # 完整的文件名列表
    possible_filenames = []
    for prefix in prefixes:
        for base in base_names:
            possible_filenames.append(f"{prefix}{base}")

    # 检查每个可能的文件名
    for filename in possible_filenames:
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            print(f"找到OCR结果文件: {file_path}")
            return file_path

    # 如果找不到固定名称文件，查找所有ocr开头的txt文件
    txt_files = [f for f in os.listdir(directory) if f.endswith(".txt") and "ocr" in f.lower()]
    if txt_files:
        # 按修改时间排序，取最新文件
        txt_files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)), reverse=True)
        newest_file = os.path.join(directory, txt_files[0])
        print(f"找到最新的OCR结果文件: {newest_file}")
        return newest_file

    # 如果找不到文件，尝试在父目录查找
    parent_dir = os.path.dirname(directory)
    for filename in possible_filenames:
        file_path = os.path.join(parent_dir, filename)
        if os.path.exists(file_path):
            print(f"在父目录找到OCR结果文件: {file_path}")
            return file_path

    print(f"在目录 {directory} 及其父目录中未找到任何OCR结果文件")
    return None

def oreadexit():
    """
    读取和分割原试卷，使用JSON格式进行数据传递，提高结构化程度和处理效率
    不需要保存学生信息，只处理题目部分
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ocr_file = os.path.join(current_dir, "oocr_results.txt")

    try:
        with open(ocr_file, "r", encoding="utf-8") as f:
            Otxt = f.read()
        f.close()
        print(Otxt)
        
        # 使用AI进行试卷分割，要求返回JSON格式
        ai_prompt = f"""
请对以下试卷内容进行分析和分割，并以JSON格式返回结果。

试卷内容:
{Otxt}

请将试卷分割为不同的大题部分（如选择题、填空题、判断题、简答题、编程题等）强调不包含学生信息，例如：姓名：_________________________等等。
对于每个大题部分，提取其标题和完整内容。

返回格式要求:
{{
    "sections": [
        {{
            "title": "一、选择题",
            "content": "完整的选择题部分内容，包括所有小题"
        }},
        {{
            "title": "二、填空题",
            "content": "完整的填空题部分内容，包括所有小题"
        }},
        // 其他大题部分...
    ]
}}

请确保:
1. 正确识别每个大题的开始和结束位置
2. 不要遗漏任何题目内容
3. 保持原始格式，不要添加或删除信息
4. 只返回JSON格式数据，不要有任何其他文字
"""
        json_result = new("你是一个专业的试卷分析助手", ai_prompt)
        
        # 解析JSON结果
        import json
        import re
        
        # 从回复中提取JSON部分
        json_match = re.search(r'\{.*\}', json_result, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            sections_data = json.loads(json_str)
        else:
            try:
                sections_data = json.loads(json_result)
            except json.JSONDecodeError:
                print("错误：无法解析AI返回的JSON数据")
                sections_data = {"sections": []}
        
        # 保存分割后的大题到单独文件，使用"原始卷"前缀
        if "sections" in sections_data and sections_data["sections"]:
            for section in sections_data["sections"]:
                title = section.get("title", "").strip()
                content = section.get("content", "").strip()
                
                if title and content:
                    # 去除文件名中的非法字符
                    filename = re.sub(r'[\\/:*?"<>|]', '', title)
                    # 将大题内容写入文件，使用"原始卷"前缀
                    output_file = os.path.join(current_dir, f"原始卷{filename}.txt")
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"已保存大题：{title}")
        else:
            print("警告：未能识别出任何大题部分")
            
        print("原始卷分割完成")
        return None
        
    except FileNotFoundError:
        print(f"错误：找不到文件 {ocr_file}")
        print("请确认文件路径和文件名是否正确")
        return None
    except Exception as e:
        print(f"处理文件时出错：{str(e)}")
        import traceback
        traceback.print_exc()
        return None

def extract_student_info(text):
    """
    从试卷文本中提取学生姓名、学号、科目和日期信息
    
    参数:
    text: 试卷OCR识别后的文本
    
    返回:
    包含学生信息的字典 {'姓名': '...', '学号': '...', '科目': '...', '日期': '...'}
    """
    # 使用AI辅助提取学生信息
    first_lines = '\n'.join(text.split('\n')[:15])  # 获取前15行，通常学生信息在开头
    
    ai_prompt = f"""
请从以下试卷文本中提取学生的基本信息，并以JSON格式返回。
试卷文本的开头部分如下：
{first_lines}

注意：学生信息可能有多种格式，例如：
1. 姓名: _____ 学号: _____ 科目: _____ 日期: _____
2. 姓  名: _____ 学  号: _____ 科  目: _____ 日  期: _____
3. 姓名：_____ 班级：_____ 科目：_____ 日期：_____
4. 或者其他格式

请提取所有可以找到的信息，如果某项信息未找到，对应值设为空字符串。
格式如下：
{{
    "姓名": "提取的姓名",
    "学号": "提取的学号",
    "科目": "提取的科目",
    "日期": "提取的日期"
}}

只返回JSON格式数据，不要有任何其他文字。
"""
    
    try:
        ai_response = new("你是一个信息提取助手", ai_prompt)
        # 尝试提取JSON部分
        import json
        import re
        
        # 如果回复包含其他文本，尝试提取JSON部分
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            student_info = json.loads(json_str)
        else:
            student_info = json.loads(ai_response)
        
        # 确保结果包含所有必要的键
        required_keys = ['姓名', '学号', '科目', '日期']
        for key in required_keys:
            if key not in student_info:
                student_info[key] = ""
        
        return student_info
    
    except Exception as e:
        print(f"AI辅助提取学生信息失败: {str(e)}")
        # 回退到基本正则表达式提取方法
        name_pattern = r'姓\s*名[：:]\s*([^\n]*)'
        id_pattern = r'学\s*号[：:]\s*([^\n]*)'
        class_pattern = r'班\s*级[：:]\s*([^\n]*)'
        subject_pattern = r'科\s*目[：:]\s*([^\n]*)'
        date_pattern = r'日\s*期[：:]\s*([^\n]*)'
        
        # 查找匹配
        name_match = re.search(name_pattern, text)
        id_match = re.search(id_pattern, text)
        class_match = re.search(class_pattern, text)
        subject_match = re.search(subject_pattern, text)
        date_match = re.search(date_pattern, text)
        
        # 构建结果字典
        result = {
            '姓名': name_match.group(1).strip() if name_match else "",
            '学号': id_match.group(1).strip() if id_match else "",
            '科目': subject_match.group(1).strip() if subject_match else "",
            '日期': date_match.group(1).strip() if date_match else ""
        }
        
        # 如果没有学号但有班级信息，可以使用班级信息
        if not result['学号'] and class_match:
            result['学号'] = class_match.group(1).strip()
            
        return result


def readexit(specific_ocr_file=None):
    """
    读取和分割学生已答题试卷，并提取学生信息
    使用JSON格式进行数据传递，提高结构化程度和处理效率

    参数:
    specific_ocr_file: 指定的OCR文件路径（可选）

    返回:
    学生信息字典，如果处理失败则返回None
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 如果提供了特定文件路径，则直接使用
    if specific_ocr_file and os.path.exists(specific_ocr_file):
        ocr_file = specific_ocr_file
        print(f"使用指定的OCR文件: {ocr_file}")
    else:
        # 否则查找OCR结果文件
        base_name = os.path.basename(specific_ocr_file) if specific_ocr_file else None
        ocr_file = find_ocr_file(current_dir, base_name)

    if not ocr_file:
        print("错误：无法找到OCR结果文件")
        return None

    try:
        with open(ocr_file, "r", encoding="utf-8") as f:
            Otxt = f.read()
        f.close()
        
        # 提取学生信息
        student_info = extract_student_info(Otxt)
        
        # 使用AI进行试卷分割，要求返回JSON格式
        ai_prompt = f"""
请对以下试卷内容进行分析和分割，并以JSON格式返回结果。

试卷内容:
{Otxt}

请将试卷分割为不同的大题部分（如选择题、填空题、判断题、简答题、编程题等）。
对于每个大题部分，提取其标题和完整内容。

返回格式要求:
{{
    "sections": [
        {{
            "title": "一、选择题",
            "content": "完整的选择题部分内容，包括所有小题"
        }},
        {{
            "title": "二、填空题",
            "content": "完整的填空题部分内容，包括所有小题"
        }},
        // 其他大题部分...
    ]
}}

请确保:
1. 正确识别每个大题的开始和结束位置
2. 不要遗漏任何题目内容
3. 保持原始格式，不要添加或删除信息
4. 只返回JSON格式数据，不要有任何其他文字
"""
        json_result = new("你是一个专业的试卷分析助手", ai_prompt)
        
        # 解析JSON结果
        import json
        import re
        
        # 从回复中提取JSON部分
        json_match = re.search(r'\{.*\}', json_result, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            sections_data = json.loads(json_str)
        else:
            try:
                sections_data = json.loads(json_result)
            except json.JSONDecodeError:
                print("错误：无法解析AI返回的JSON数据")
                sections_data = {"sections": []}
        
        # 保存分割后的大题到单独文件
        if "sections" in sections_data and sections_data["sections"]:
            for section in sections_data["sections"]:
                title = section.get("title", "").strip()
                content = section.get("content", "").strip()
                
                if title and content:
                    # 去除文件名中的非法字符
                    filename = re.sub(r'[\\/:*?"<>|]', '', title)
                    # 将大题内容写入文件
                    output_file = os.path.join(current_dir, f"{filename}.txt")
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"已保存大题：{title}")
        else:
            print("警告：未能识别出任何大题部分")
        
        # 保存学生信息到单独文件
        if student_info:
            output_file = os.path.join(current_dir, "student_info.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                for key, value in student_info.items():
                    f.write(f"{key}: {value}\n")
            
            # 输出提取的学生信息
            print("\n提取的学生信息:")
            for key, value in student_info.items():
                print(f"{key}: {value}")
        else:
            print("\n未能提取到学生信息")
        
        # 临时保存处理结果为JSON文件（仅用于调试，处理完成后会删除）
        json_temp_file = os.path.join(current_dir, "exam_analysis_temp.json")
        result_data = {
            "student_info": student_info,
            "sections": sections_data.get("sections", [])
        }
        
        # 临时保存JSON文件（用于调试）
        with open(json_temp_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"数据处理完成，已生成所有分割文件")
        
        # 处理完成后删除临时JSON文件
        if os.path.exists(json_temp_file):
            os.remove(json_temp_file)
            print(f"已删除临时JSON文件")
        
        return student_info
        
    except FileNotFoundError:
        print(f"错误：找不到文件 {ocr_file}")
        print("请确认文件路径和文件名是否正确")
        return None
    except Exception as e:
        print(f"处理文件时出错：{str(e)}")
        import traceback
        traceback.print_exc()
        
        # 确保即使出错也会尝试删除临时文件
        json_temp_file = os.path.join(current_dir, "exam_analysis_temp.json")
        if os.path.exists(json_temp_file):
            try:
                os.remove(json_temp_file)
                print(f"已删除临时JSON文件")
            except:
                pass
        
        return None

if __name__ == '__main__':
    import sys
    
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 查找OCR结果文件
    ocr_file = find_ocr_file(current_dir)
    
    if not ocr_file:
        print("尝试处理失败：未找到OCR结果文件")
        print("可能的原因：")
        print("1. OCR结果文件尚未生成")
        print("2. OCR结果文件名称不正确")
        print("3. OCR结果文件位置不正确")
        print("\n请确保以下文件之一存在：")
        print(f"- {os.path.join(current_dir, 'ocr_results.txt')}")
        print(f"- {os.path.join(current_dir, '@ocr_results.txt')}")
        print(f"- {os.path.join(current_dir, 'oocr_results.txt')}")
        sys.exit(1)
    
    print(f"\n正在处理OCR结果文件: {ocr_file}")
    print("========================================")
    
    try:
        # 处理文件并提取学生信息
        student_info = readexit()
        
        if student_info:
            print("\n学生信息处理成功!")
            print("----------------------------------------")
            print("提取的学生信息:")
            for key, value in student_info.items():
                if value:  # 只打印非空信息
                    print(f"{key}: {value}")
            print("----------------------------------------")
        else:
            print("\n警告：未能提取到学生信息或处理过程中出现错误")
        
        print("\n题目分割处理完成。")
        
        # 查找生成的文件
        txt_files = [f for f in os.listdir(current_dir) if f.endswith(".txt") and f not in ["ocr_results.txt", "@ocr_results.txt", "oocr_results.txt"]]
        if txt_files:
            print("\n已生成以下文件:")
            for file in sorted(txt_files):
                print(f"- {file}")
        
        print("\n处理完成。")
        sys.exit(0)
    except Exception as e:
        print(f"\n处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)