# -*- coding: utf-8 -*-
import subprocess
import requests
import influxdb_op
import sys
import configparser
import os

# DeepSeek API 配置
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# SVN 配置
SVN_REPO_PATH = "https://desktop-xxxxx/svn/test"  # 替换为你的 SVN 仓库路径
SVN_REVISION = ""  # 替换为你要比较的版本号，例如 "123" 或 "HEAD"
SVN_USER = ""  #svn用户名
SVN_PWD = ""  #svn用户名密码
PROUCT_ID = "" #产品id

def get_revisions_and_authors(repo_path, start_revision):
    """
    获取从指定版本到最新版本的版本号和提交人信息。
    :param repo_path: SVN 仓库路径
    :param start_revision: 起始版本号
    :return: 版本号和提交人信息的列表（元组列表）
    
    """
    try:
        # 执行 svn log 命令，获取从指定版本到最新版本的日志
        command = ["svn", "log", "-q", "-r", f"{start_revision}:HEAD", repo_path ,"--username", SVN_USER, "--password", SVN_PWD, "--non-interactive","--trust-server-cert"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        log_lines = result.stdout.strip().split("\n")

        # 提取版本号和提交人信息
        revisions_authors = []
        for line in log_lines:
            if line.startswith("r"):
                parts = line.split("|")
                revision = parts[0].strip()[1:]  # 提取版本号（去掉开头的 'r'）
                author = parts[1].strip()  # 提取提交人
                revisions_authors.append((revision, author))

        return revisions_authors
    except subprocess.CalledProcessError as e:
        print("Error executing svn log: {}".format(e))
        return None


def get_svn_diff(repo_path, revision1, revision2):
    """
    获取两个版本之间的代码差异。
    :param repo_path: SVN 仓库路径
    :param revision1: 较新的版本号
    :param revision2: 较旧的版本号
    :param user_name: svn 账户
    :param user_passwd: svn 账户密码
    :return: 代码差异（字符串）
    """
    try:
        # 执行 svn diff 命令
        command = ["svn", "diff", "-r", f"{revision2}:{revision1}", repo_path,"--username", SVN_USER, "--password", SVN_PWD, "--non-interactive","--trust-server-cert"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        result = "\n".join(line for line in result.stdout.splitlines() if "No newline at end of file" not in line)
        
        # 存储文件名和对应的代码内容
        file_code_map = {}
        current_file = None
        current_code = []

        # 按行处理输出
        for line in result.splitlines():
            if line.startswith('Index:'):
                # 保存上一个文件的代码（如果存在）
                if current_file:
                    file_code_map[current_file] = '\n'.join(current_code)

                # 提取当前文件名
                current_file = line.split(':', 1)[1].strip()
                current_code = [line]  # 当前行作为新文件的第一行
            else:
                # 收集当前文件的代码内容
                if current_file:
                    current_code.append(line)

        # 保存最后一个文件的代码
        if current_file:
            file_code_map[current_file] = '\n'.join(current_code)
        
        return file_code_map
    except subprocess.CalledProcessError as e:
        print("Error executing svn diff: {}".format(e))
        return None



def send_to_deepseek(code_diff):
    """
    将代码差异发送给 DeepSeek 审查。
    :param code_diff: 代码差异（字符串）
    :return: DeepSeek 的响应结果
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user",
                "content": f"请审查以下代码差异：\n{code_diff}"
            }
        ]
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()  # 检查 HTTP 错误
        
         # 解析 JSON 响应并提取 content 字段
        response_json = response.json()
        content = response_json["choices"][0]["message"]["content"]
        return content
    except requests.exceptions.RequestException as e:
        print("Error sending request to DeepSeek: {}".format(e))
        return None
    except KeyError as e:
        print("Error parsing DeepSeek response: {}".format(e))
        return None


def main():
    # 获取 SVN 代码差异
    print("Fetching revisions and authors...")
    revisions_authors = get_revisions_and_authors(SVN_REPO_PATH, SVN_REVISION)
    if not revisions_authors:
        print("Failed to get revisions and authors.")
        return

    # 依次比较相邻版本的代码差异
    for i in range(1, len(revisions_authors)):
        revision1, author1 = revisions_authors[i]
        revision2, author2 = revisions_authors[i - 1]

        print(f"\nComparing revisions: {revision2} (by {author2}) -> {revision1} (by {author1})")
        file_path = f"{PROUCT_ID}_svn_version"
        with open(file_path, 'w') as f:
            f.write(revision1)
        # 获取 SVN 代码差异
        print("Fetching SVN diff...")
        code_diff = get_svn_diff(SVN_REPO_PATH, revision1, revision2)
        if not code_diff:
            print("Failed to get SVN diff.")
            continue

        print("SVN diff fetched successfully.")

        # 打印代码差异
        print("\n--- Code Diff ---")
        #print(code_diff)
        for file_name, code in code_diff.items():
            print(f"文件名: {file_name}")
            print(f"代码内容:{code}")
        
            
            # 发送代码差异给 DeepSeek 审查
            print("Sending code diff to DeepSeek for review...")
            review_content = send_to_deepseek(code)
            if not review_content:
                print("Failed to get review result from DeepSeek.")
                continue

            # 输出审查结果（仅 content 字段）
            print("Review result from DeepSeek:")
            print(review_content)
            
            # 写到influxdb中
            influxdb_op.insertData(PROUCT_ID,author1,revision1,file_name,code,review_content)
            
            '''
            # 将结果保存到文件
            with open(f"review_{revision2}_{revision1}.txt", "w", encoding="utf-8") as f:
                f.write(f"Comparing revisions: {revision2} (by {author2}) -> {revision1} (by {author1})\n")
                f.write("--- Code Diff ---\n")
                f.write(code)
                f.write("\n-----------------\n")
                f.write("Review result from DeepSeek:\n")
                f.write(review_content)
                f.write("\n")
            print(f"Review result saved to review_{revision2}_{revision1}.txt")
            '''
            
        print("-----------------\n")
        
        continue
        
def setGlobalValue(p_id,url_path,user_name,user_pwd):
    global SVN_REPO_PATH
    SVN_REPO_PATH=url_path
    global SVN_USER
    SVN_USER=user_name
    global SVN_PWD
    SVN_PWD = user_pwd
    global PROUCT_ID
    PROUCT_ID = p_id

def readInifile():
    # 创建 ConfigParser 对象
    config = configparser.ConfigParser()
    # 读取 ini 文件
    config.read('config.ini')
    product_id = []
    for key, value in config.items('product_id'):
        product_id.append(value)
    return product_id

def getLastCheckSvnVersion():
    #先判断文件是否存在
    file_path = f"{PROUCT_ID}_svn_version"
    global SVN_REVISION
    if os.path.exists(file_path):
        print(f"文件 '{file_path}' 存在")
        with open(file_path, 'r') as file:
            content = file.read()
            print(content)
            SVN_REVISION=content
    else:
        print(f"文件 '{file_path}' 不存在")
        #读取svn最后一个svn version
        try:
            # 执行 svn log 命令，获取从指定版本到最新版本的日志
            command = ["svn", "log", "-l","1", "-r", "HEAD", SVN_REPO_PATH ,"--username", SVN_USER, "--password", SVN_PWD, "--non-interactive","--trust-server-cert"]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            log_lines = result.stdout.strip().split("\n")

            # 提取版本号
            revisions_authors = []
            for line in log_lines:
                if line.startswith("r"):
                    parts = line.split("|")
                    revision = parts[0].strip()[1:]  # 提取版本号（去掉开头的 'r'）
                    with open(file_path, 'w') as f:
                        f.write(revision)
                    SVN_REVISION=revision

           
        except subprocess.CalledProcessError as e:
            print("Error executing svn log: {}".format(e))
    
    

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("用法: python3 code_review.py <产品id> <svn地址> <svn用户名> <svn密码>")
        sys.exit(1)
    pdt_ids = readInifile()
    print(f"ids:{pdt_ids}")
    p_id = sys.argv[1]
    svn_url = sys.argv[2]
    user_name = sys.argv[3]
    user_pwd = sys.argv[4]
    print(f"参数1: {p_id}")
    print(f"参数2: {svn_url}")
    print(f"参数2: {user_name}")
    print(f"参数2: {user_pwd}")
    if p_id not in pdt_ids:
        print(f"'{p_id}' 不在产品ID列表中！")
    setGlobalValue(p_id,svn_url,user_name,user_pwd)
    getLastCheckSvnVersion()
    main()