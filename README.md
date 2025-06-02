# Co-Traveller

A group assignment for Peking University, an agent that helps you make travel plans.

## 依赖说明

本项目需要以下依赖：

1. **Pandoc**
    - 用于 Markdown 转 PDF（可选方案）。
    - 请从 [Pandoc 官网](https://pandoc.org/installing.html) 下载并安装。
    - 安装后请确保 `pandoc` 命令已加入环境变量 PATH，否则无法直接在命令行或 bat 脚本中调用。

2. **wkhtmltopdf**
    - 用于 Markdown 转 PDF（推荐方案，配合 `md2pdf_wkhtmltopdf.py` 使用）。
    - 请从 [wkhtmltopdf 官网](https://wkhtmltopdf.org/downloads.html) 下载并安装。
    - 安装后请确保其可执行文件路径在下列常见路径之一，或已添加到环境变量 PATH 中：
        - Windows:  
          `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`  
          `C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe`
        - Linux/macOS:  
          `/usr/local/bin/wkhtmltopdf`  
          `/usr/bin/wkhtmltopdf`

3. **Python 依赖包**
    - 请通过 pip 安装：
      ```
      pip install -r requirements.txt
      ```
    - 主要依赖：
        - `markdown`
        - `pdfkit`
        - `python-dotenv`  # 用于环境变量加载

## 知识库准备（PDF 旅行攻略）

由于 `src/utils/rag_helper.py` 需要为大模型提供知识库，请在项目根目录下新建一个名为 `dataset` 的文件夹，并将你的 PDF 旅行攻略文件放入其中。  
每次运行检索功能时，系统会自动加载该文件夹下的所有 PDF 文档作为知识库。

## API 密钥配置

请在项目根目录下新建或编辑 `API.env` 文件，并写入如下内容（将密钥替换为你自己的）：
```
SILICON_API_KEY=你的API密钥
```
**注意：** `API.env` 文件已被 `.gitignore` 忽略，请勿将密钥提交到公共仓库。

如需更多帮助，请参考各工具的官方文档。
