from openai import OpenAI
import json
import httpx
import os

def aiapi(line):
    try:
        client = OpenAI(
            api_key="sk-43e4fcb551e544ce896f63bce4a44678", 
            base_url="https://api.deepseek.com",
            timeout=30.0
        )
        
        messages = [{"role": "user", "content": f"{line}"}]
        
        response = client.chat.completions.create(
            # model='deepseek-reasoner',
            model="deepseek-chat",
            messages=messages
        )
        
        return response.choices[0].message.content
        
    except httpx.ConnectError as e:
        print(f"API连接错误: {str(e)}")
        return ""
    except json.JSONDecodeError as e:
        print(f"响应解析错误: {str(e)}")
        return ""
    except Exception as e:
        print(f"其他错误: {str(e)}")
        return ""


def new(line1,line2):
    client = OpenAI(api_key="sk-43e4fcb551e544ce896f63bce4a44678", base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"{line1}"},
            {"role": "user", "content": f"{line2}"},
        ],
        stream=False
    )

    return response.choices[0].message.content

if __name__ == '__main__':
    print(new("你是一个天气助手", "请告诉我今天的天气"))
