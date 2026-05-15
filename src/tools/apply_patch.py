def write_file(file_path: str, content: str):

    #defensive for when llm double \\n have not figure out why yet
    content_write = content   
    if "\\n" in content and "\n" not in content:
        content_write = content.encode("utf-8").decode("unicode_escape")

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content_write)
        return {"path": file_path, "status": "written", "content": content}
    
    return {"path": file_path, "status": "failed"}

def read_file(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return {"path": file_path, "content": file.read()}
    
    return {"path": file_path, "status": "failed"}