def write_file(file_path: str, content: str):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

def read_file(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        return {"path": file_path, "content": file.read()}