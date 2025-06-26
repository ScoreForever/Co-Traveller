from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from pathlib import Path
import fitz
import os
import gradio as gr
import requests
import sseclient
import json

# 远程 Qwen API 流式响应封装
# def stream_qwen_response(prompt):
#     api_key = os.getenv("sub_SILICON_API_KEY")
#     if not api_key:
#         raise ValueError("请设置 sub_SILICON_API_KEY 环境变量")

#     headers = {
#         "Authorization": f"Bearer {api_key}",
#         "Accept": "text/event-stream",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "model": "Qwen/Qwen3-8B",
#         "stream": True,
#         "messages": [
#             {"role": "system", "content": "你是一个友好的中文助手。"},
#             {"role": "user", "content": prompt}
#         ]
#     }
def stream_qwen_response(prompt):
    import os
    import requests
    import json

    api_key = os.getenv("SILICON_API_KEY")
    if not api_key:
        raise ValueError("请设置 SILICON_API_KEY 环境变量")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "Qwen/Qwen3-8B",
        "stream": True,
        "messages": [
            {"role": "system", "content": "你是一个友好的中文助手。"},
            {"role": "user", "content": prompt}
        ]
    }

    with requests.post("https://api.siliconflow.cn/v1/chat/completions", headers=headers, json=payload, stream=True) as response:
        if response.status_code != 200:
            raise RuntimeError(f"请求失败：{response.status_code} {response.text}")
        response.encoding = "utf-8"
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            data = line.removeprefix("data: ").strip()
            if data == "[DONE]":
                break

            try:
                delta = json.loads(data)
                content = delta.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if content:
                    yield content
            except json.JSONDecodeError as e:
                # 不再输出报错，避免污染 UI 显示
                continue

    with requests.post("https://api.siliconflow.cn/v1/chat/completions", headers=headers, json=payload, stream=True) as response:
        if response.status_code != 200:
            raise RuntimeError(f"请求失败：{response.status_code} {response.text}")

        # 检查是否为流式返回
        if "text/event-stream" not in response.headers.get("Content-Type", ""):
            raise RuntimeError(f"不是 SSE 流式返回，而是：{response.headers.get('Content-Type')}")
        client = sseclient.SSEClient(response)
        for event in client.events():
            if event.data == "[DONE]":
                break
            try:
                delta = json.loads(event.data)
                content = delta.get("choices", [{}])[0].get("delta", {}).get("content", "")
                yield content
            except Exception as e:
                yield f"[流式解析错误] {e}"

# 加载 PDF 文件夹
def load_pdfs_from_folder(folder_path):
    documents = []
    for file in Path(folder_path).rglob("*.pdf"):
        try:
            text = ""
            with fitz.open(str(file)) as doc:
                for page in doc:
                    text += page.get_text()
            if text.strip():
                documents.append(Document(page_content=text, metadata={"source": str(file)}))
        except Exception as e:
            print(f"读取失败: {file} 原因: {e}")
    return documents

# 构建仅检索的向量检索器
def build_retriever_from_docs(documents):
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)
    if not chunks:
        raise ValueError("文档内容为空，无法构建向量数据库")

    # embedder = HuggingFaceEmbeddings(
    #     model_name="./models/bge-small-zh",
    #     model_kwargs={"device": "cpu"}
    # )

    # 以当前 travel.py 所在的 src 目录为基准
    src_dir = Path(__file__).resolve().parent.parent
    model_path = src_dir / "models" / "bge-small-zh"

    # 使用绝对路径初始化嵌入模型
    embedder = HuggingFaceEmbeddings(
        model_name=str(model_path),
        model_kwargs={"device": "cpu"}
    )
    


    vectordb = FAISS.from_documents(chunks, embedder)
    return vectordb.as_retriever(search_kwargs={"k": 10})

# 构建搜索函数（对检索结果进行流式总结）
def stream_search_docs(query, retriever):
    results = retriever.invoke(query)  # 使用新版 API
    if not results:
        yield "未找到相关内容"
        return

    filtered = [doc for doc in results if query.lower() in doc.page_content.lower()]
    if not filtered:
        yield "未找到包含关键词的内容，请尝试换个表达"
        return

    combined_text = "\n".join(doc.page_content[:1000] for doc in filtered[:5])
    try:
        prompt = f"请根据以下内容生成简洁清晰的旅游推荐摘要：\n\n{combined_text}\n\n摘要："
        for chunk in stream_qwen_response(prompt):
            yield chunk
    except Exception as e:
        #yield f"大模型总结失败：{e}，改为显示原文：\n\n{combined_text}"
        return

# 加载环境变量
def load_env(filepath):
    env = {}
    if os.path.exists(filepath):
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

if __name__ == "__main__":
    env_path = Path(__file__).resolve().parent.parent / "API.env"
    env_vars = load_env(env_path)
    os.environ.update(env_vars)

    dataset_dir = Path(__file__).resolve().parent.parent / "dataset"
    #dataset_dir = Path("./dataset").resolve()
    #dataset_dir = Path("dataset").resolve()
    rag_docs = load_pdfs_from_folder(dataset_dir)
    if not rag_docs:
        raise RuntimeError("PDF 文件夹中未成功加载任何文档，请检查 dataset 路径与 PDF 内容")
    retriever = build_retriever_from_docs(rag_docs)

    # dataset_dir = Path(__file__).resolve().parent.parent / "dataset"
    # # 打印调试信息，方便排查问题
    # print(f"📂 正在加载 dataset 文件夹路径: {dataset_dir}")
    # if not dataset_dir.exists():
    #     raise FileNotFoundError(f"找不到 dataset 文件夹，请确认路径是否存在: {dataset_dir}")

    # 加载 PDF 文档
    rag_docs = load_pdfs_from_folder(dataset_dir)
    if not rag_docs:
        raise RuntimeError("❌ PDF 文件夹中未成功加载任何文档，请检查 dataset 路径与 PDF 内容")

    # 构建检索器
    retriever = build_retriever_from_docs(rag_docs)

    with gr.Blocks() as demo:
        with gr.Tab("📚 文档问答助手"):
            gr.Markdown("### 输入关键词（如城市名），从PDF文档中检索相关内容并由大模型优化输出（流式响应）")

            with gr.Row():
                user_query = gr.Textbox(label="输入问题", placeholder="例如：北京")
                ask_btn = gr.Button("检索文档", variant="primary")

            with gr.Row():
                rag_answer = gr.Textbox(label="检索结果", lines=15, interactive=False)

            def query_docs_with_rag_stream(query):
                if not query.strip():
                    yield "请输入问题"
                    return
                yield from stream_search_docs(query, retriever)

            ask_btn.click(fn=query_docs_with_rag_stream, inputs=[user_query], outputs=[rag_answer], stream=True)

        demo.launch()
