import questionsplit
import fill_question
import true_false_questions
import multiple_choice_questions
import programming_questions
import short_answer_questions
import os
import re
from split_and_ocr.ai import aiapi


class AIExam:
    @staticmethod
    def remove_txt(name):
        files = [f for f in os.listdir() if f.endswith('.txt')]
        # 匹配包含指定名称且文件名长度大于2的文件
        fill_files = [f for f in files if re.search(rf'{name}.+', f)]
        if fill_files:
            os.remove(fill_files[0])

    @staticmethod
    def run_slip(subject, user_id):
        count = 0
        questionsplit.readexit()
        fianswers, fillaa = fill_question.fill_readexit()
        for i, j in zip(fianswers, fillaa):
            if i == j:
                count += 1
        chanswers, chaa = multiple_choice_questions.choice_readexit(subject, user_id)
        for i, j in zip(chanswers, chaa):
            if i == j:
                count += 1
        proanswers,proaa = programming_questions.pro_readexit()
        for i, j in zip(proanswers, proaa):
            line = f"{i}和{j}两端编程输出是一样的吗？只输出是或者否"
            k = aiapi(line)
            if k == '是':
                count += 5

        ananswers,anaa = short_answer_questions.answer_readexit()
        for i, j in zip(ananswers, anaa):
            for k in j.split("|"):
                if k is None:
                    continue
                else:
                    if k in i:
                        count += 2
        tfanswers ,tfaa = true_false_questions.tf_readexit()
        for i, j in zip(tfanswers, tfaa):
            if i == j:
                count += 1
        print(count)
        for i in ["填空","选择","编程","简答","判断"]:
            AIExam.remove_txt(i)
        return count

    @staticmethod
    def run_ocr(subject, user_id):
        try:
            # 确保在正确的目录中操作
            current_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(current_dir)
            
            questionsplit.oreadexit()
            fill_question.ofill_readexit(subject, user_id)
            multiple_choice_questions.choice_readexit(subject, user_id)
            programming_questions.pro_readexit(subject, user_id)
            short_answer_questions.answer_readexit(subject, user_id)
            true_false_questions.tf_readexit(subject, user_id)
            print("题库更新完成")
            for i in ["填空","选择","编程","简答","判断"]:
                AIExam.remove_txt(i)
            return True
        except Exception as e:
            print(f"题库更新失败: {str(e)}")
            return False

# 创建一个实例供外部使用
aiexam = AIExam()

if __name__ == '__main__':
    AIExam.run_ocr(subject="python", user_id=1)