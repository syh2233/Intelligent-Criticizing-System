from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os
import ai
import threading


class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        """
        当有文件在 Ovolume 文件夹中创建时触发
        """
        if not event.is_directory:  # 确保是文件创建，而非文件夹
            print(f"文件创建了: {event.src_path}")
            if os.path.exists("split_and_ocr/read/ocr_results.txt"):
                os.remove("split_and_ocr/read/ocr_results.txt")
            # 调用 slip.py 中的 split_columns_and_rows 函数处理图片
            from slip import split_columns_and_rows
            split_columns_and_rows(event.src_path)
            os.remove(event.src_path)
            print("图片已传递给 slip.py 进行处理")
            ai.readexit()



def monitor_folder(path, handler):
    """
    监听指定文件夹
    """
    observer = Observer()
    observer.schedule(handler, path, recursive=False)  # 不递归子目录
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    # 创建线程分别监听两个文件夹
    thread1 = threading.Thread(target=monitor_folder, args=("Ovolume", MyHandler()))

    # 启动线程
    thread1.start()

    # 等待线程完成
    thread1.join()
