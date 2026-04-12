# tests/test_converter.py
import pytest
from pathlib import Path
from src.converter import Converter

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

@pytest.fixture
def html_fixture():
    return Path("tests/fixtures/html_sample.html").read_text()

def test_convert_html_to_markdown(html_fixture, temp_dir):
    converter = Converter(str(temp_dir))
    md = converter.convert_html(html_fixture)
    assert "# 标题" in md
    assert "段落内容" in md

def test_passthrough_markdown(temp_dir):
    converter = Converter(str(temp_dir))
    content = "# 已有标题\n\n正文内容"
    result = converter.convert(content, note_type="plain_text")
    assert result == content

def test_convert_link_note(temp_dir):
    converter = Converter(str(temp_dir))
    html = "<html><body><h1>标题</h1><p>内容</p></body></html>"
    result = converter.convert(html, note_type="link")
    assert "# 标题" in result
