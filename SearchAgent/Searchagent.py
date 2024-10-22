import requests
from bs4 import BeautifulSoup
from promptSet import prompt,user_agent_pool
import torch
import re
import random
import concurrent.futures
from urllib.parse import urlparse
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional
from readability import Document
import chardet
import time
import os
from modelSet import getModel
import argparse

TIMEOUT=1.5 # 网页请求超时时间
MAX_TOKENS=4000 # 网页+问题的输入文本最大长度
black_list: Optional[List[str]] = [
    'enoN', 'researchgate.net','zhihu.com' # 知乎爬不下来，知乎好像有api。
]

video_sites = [
    "youtube.com", "vimeo.com", "dailymotion.com", "youku.com",
    "bilibili.com", "v.qq.com", "iqiyi.com", "netflix.com",
    "hulu.com", "primevideo.com"
]

all_filtered_sites = list(set(video_sites + black_list))

def is_video_site(url):
    """判断链接是否属于常见视频网站"""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    return any(filtered_site in domain for filtered_site in all_filtered_sites)

def filtByTFIDF(query, results, top_n=1):
    # 计算TF-IDF特征,去选择最相关的结果
    titles=[result["title"] for result in results]
    vectorizer = TfidfVectorizer().fit_transform([query] + titles)
    vectors = vectorizer.toarray()
    
    # 计算相似度
    cosine_similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    
    # 根据相似度对结果进行排序
    sorted_indices = cosine_similarities.argsort()[::-1][:top_n]
    filtered_results = [results[i] for i in sorted_indices]
    
    return filtered_results


def baidu_search(query, max_results=5, top_n=1,timeout=TIMEOUT):
    """从百度搜索中获取搜索结果并过滤无关链接"""
    # 构建百度搜索的URL
    url = f"https://www.baidu.com/s?wd={query}"
    
    # 发送GET请求
    headers = {
        "User-Agent": random.choice(user_agent_pool)}
    try:
        response = requests.get(url, headers=headers,timeout=timeout)
    except requests.RequestException as e:
        print(f"无法访问 {url}: {e}")
        return []

    # 解析HTML内容
    soup = BeautifulSoup(response.text, "html.parser")
    
    # 提取搜索结果标题和链接
    results = []
    for item in soup.find_all('h3', class_='t'):
        if len(results) >= max_results:
            break
        title = item.get_text()
        link = item.a['href']
        
        # 过滤掉常见视频网站的链接
        if not is_video_site(link):
            results.append({"title": title, "link": link, "query": query})
    
    if len(results) <= top_n:
        return results

    return filtByTFIDF(query, results, top_n=top_n)



def decodeQList(output_text):
    # 使用正则表达式匹配列表中的每个子问题
    # 假设子问题列表格式为 ["子问题1", "子问题2", ...]
    pattern = r'"\s*(.*?)\s*"'
    matches = re.findall(pattern, output_text)
    
    # 提取出每个子问题并返回一个列表
    sub_questions = [match for match in matches]
    
    return sub_questions


def splitQ(query):
    # 使用模型生成文本
    context=prompt['splitQ'].format(question=query)
    response = getModelResultByLLM(context)
    # Print the response text
    query_list = decodeQList(response)
    query_list = [query] + query_list
    query_list = list(Counter(query_list).keys())
    print(query_list)
    return query_list


def fetch_page_content_old(link):
    headers = {
        "User-Agent": random.choice(user_agent_pool)
    }
    try:
        response = requests.get(link, headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 选取主要内容的可能标签
        main_content = soup.find('article') or soup.find('div', class_='content') or soup.find('div', class_='main') or soup.find('div', class_='article-body')
        
        # 如果找不到指定的内容块，则使用 <p> 标签作为默认内容
        if main_content:
            paragraphs = main_content.find_all('p')
        else:
            paragraphs = soup.find_all('p')

        # 过滤掉可能的无关内容
        content = '\n'.join([p.get_text() for p in paragraphs if p.get_text(strip=True)])

        return content.strip() if content else None

    except requests.RequestException as e:
        print(f"无法访问 {link}: {e}")
        return None

def is_page_valid(text, threshold=0.8):
    # 过滤乱码和无效内容的网页
    # 使用正则表达式匹配中文字符
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    # 匹配数字
    digit_pattern = re.compile(r'\d')
    # 匹配英语字母
    english_pattern = re.compile(r'[a-zA-Z]')
    # 匹配中英文常见标点符号
    punctuation_pattern = re.compile(r'[，。？！：；、“”‘’《》〈〉【】\[\](),.!?\'":;]')

    # 确保文本不为空
    if not text or len(text) == 0:
        return False  # 如果文本为空，认为是乱码

    total_count = len(text)

    # 统计中文、数字、英语字符和标点符号的数量
    valid_count = (
        len(chinese_pattern.findall(text)) +
        len(digit_pattern.findall(text)) +
        len(english_pattern.findall(text)) +
        len(punctuation_pattern.findall(text))
    )
    
    # 计算有效字符比例
    valid_ratio = valid_count / total_count

    # 如果有效字符比例超过阈值，则返回True表示内容有效，否则返回False
    return valid_ratio >= threshold


def clean_html_content(html_content):
    # 去除 HTML 标签
    soup = BeautifulSoup(html_content, "html.parser")
    text = soup.get_text()

    # 移除多余的空行和空格
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # 去除常见的符号和无关内容
    text = re.sub(r'[<>|*{}]', '', text)

    return text


def fetch_page_content(url,timeout=TIMEOUT):
    headers = {
        "User-Agent": random.choice(user_agent_pool),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
    }
    try:
        with requests.Session() as session:
            session.headers.update(headers)
            
            # 使用Session获取页面内容
            response = session.get(url, timeout=timeout)
            response.raise_for_status()  # 检查请求是否成功
            detected_encoding = chardet.detect(response.content)['encoding']
            if detected_encoding:
                response.encoding = detected_encoding  # 设置检测到的编码
            doc = Document(response.text)
            content = doc.summary()
            # 清理内容
            cleaned_content = clean_html_content(content)
    except requests.RequestException as e:
        print(f"Error fetching content from {url}: {e}")
        return None 
    return cleaned_content


# 检查是否为重定向链接并返回最终的链接（如果有重定向）
def resolve_redirect(link):
    try:
        # 检查是否为重定向链接
        response = requests.head(link, allow_redirects=False)
        if 300 <= response.status_code < 400:
            # 重定向链接，获取重定向目标
            redirect_url = response.headers.get('Location')
            if redirect_url:
                return redirect_url  # 返回重定向后的目标链接
        return link  # 如果没有重定向，返回原始链接
    except Exception as e:
        print(f"Error checking redirection for {link}: {e}")
        return link  # 出错时返回原始链接

def cleanResults(search_results,redirect=True):
    # 排除重复的link和None值
    filtered_results = []
    if not redirect:
        for loc,result in enumerate(search_results):
            if result is None or result["link"] in [res["link"] for res in filtered_results]:
                continue
            filtered_results.append(result)
            # 并行检查重定向并替换链接
    else:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            resolved_links = executor.map(lambda result: resolve_redirect(result["link"]), search_results)
            # 遍历 search_results，并根据返回的 resolved_links 更新链接
            for result, final_link in zip(search_results, resolved_links):
                if any(site in final_link for site in black_list + video_sites):
                    continue

                # 检查重复的链接
                if final_link in [res["link"] for res in filtered_results]:
                    continue

                # 更新结果中的链接为重定向目标（如果有）
                result["link"] = final_link
                filtered_results.append(result)
    return filtered_results

def search(query,mainTopn=3,subTopn=1,summary=True,splitQFlag=True):
    # 拆分问题为子问题，增加上原问题并去重
    if splitQFlag:
        query_list = splitQ(query)
    else:
        query_list = [query]

    # 使用并行的方式搜索每个子问题
    search_results = []
    top_nSet=[mainTopn] + [subTopn]*(len(query_list)-1)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(lambda loc_q: baidu_search(loc_q[1], max_results=5, top_n=top_nSet[loc_q[0]]), enumerate(query_list))
        for result in results:
            search_results.extend(result)

    print(search_results)
    # 过滤掉重复的链接和None值
    search_results=cleanResults(search_results)

    # 并行爬取每个链接的内容
    page_contents = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        links = [result["link"] for result in search_results]
        contents = executor.map(fetch_page_content, links)
        # 将结果按顺序添加回 search_results 中
        for result, content in zip(search_results, contents):
            if content and is_page_valid (content):
                result["content"] = content
                page_contents.append(result)


    if summary:
        return summaryResultByLLM(page_contents)
    return page_contents


def getModelResultByLLM(text,max_tokens=MAX_TOKENS):
    # 使用模型生成文本
    text=text[:min(max_tokens, len(text))]
    text = tokenizer.apply_chat_template(
        [{"role": "user", "content": text}],
        tokenize=False,
    add_generation_prompt=True
    )
    model_inputs = tokenizer([text], return_tensors="pt")['input_ids'].to(device)
    # input_text= tokenizer.decode(model_inputs[0], skip_special_tokens=True)
    # print(f"输入文本: {input_text}")
    # 在不更新梯度的情况下生成结果
    with torch.no_grad():
        generated_ids = model.module.generate(
            input_ids=model_inputs,
            max_new_tokens=max_new_tokens,
        )

    # 确保正确计算生成的token，并排除输入部分
    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs, generated_ids)
    ]
    
    # 将生成的token ID解码为可读文本
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    return response

def summaryResultByLLM(page_contents):
    # 将搜索结果和子问题拼接成一个文本，并使用模型筛选关键信息
    link=[content["link"] for content in page_contents]
    main_query = page_contents[0]['query']
    mainAnswer = ""
    subq=""
    answer=""
    query =None
    for loc, content in enumerate(page_contents):
        if content['query'] == main_query:
            mainAnswer+=prompt['pageItem'].format(id=loc, content=content['content'])
        elif content['query'] == query:
            answer+=prompt['pageItem'].format(id=loc, content=content['content'])
        else:
            if query:
                subq+=prompt['subq'].format(subq=query,answers=answer,subqLast=prompt['subq'])
            query = content['query']
            answer=prompt['pageItem'].format(id=loc, content=content['content'])
    if query:
        if subq!="":
            subq=subq.format(subq=query,answers=answer,subqLast="")
        else:
            subq=prompt['subq'].format(subq=query,answers=answer,subqLast="")
    context=prompt['summary'].format(question=main_query,answers=mainAnswer,subq=subq)
    infrence_time = time.time()
    response=getModelResultByLLM(context)
    infrence_time = time.time()-infrence_time
    print(f"总结推理时间: {infrence_time:.2f}秒")
    return response, link

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="解析模型相关参数的示例。")
    parser.add_argument('--qury', type=str, default="请问NLP是什么？", help='所提问的问题')
    parser.add_argument('--model_path', type=str, default="/home/nfs02/model/Qwen1.5-14B-Chat", help='模型路径')
    parser.add_argument('--max_new_tokens', type=int, default=500, help='生成文本的最大长度')
    parser.add_argument('--summary', type=bool, default=True, help='是否生成总结')
    parser.add_argument('--splitQFlag', type=bool, default=True, help='是否分割子问题')
    parser.add_argument('--mainTopn', type=int, default=3, help='主任务的 top n 网页选择')
    parser.add_argument('--subTopn', type=int, default=1, help='子任务的 top n 网页选择')
    args = parser.parse_args()

    model_path = args.model_path
    model, tokenizer, device = getModel(model_path)

    max_new_tokens = args.max_new_tokens
    print(search(args.qury,mainTopn=args.mainTopn,subTopn=args.subTopn,summary=args.summary,splitQFlag=args.splitQFlag))