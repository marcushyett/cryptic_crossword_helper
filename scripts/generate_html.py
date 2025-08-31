#!/usr/bin/env python3
import json
import sys

def generate_html(template_file, data_file, output_file):
    with open(template_file, 'r') as f:
        template = f.read()
    
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # Replace placeholders
    html = template.replace('{{TITLE}}', data['title'])
    html = html.replace('{{GAME_DATA}}', json.dumps(data))
    
    with open(output_file, 'w') as f:
        f.write(html)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python generate_html.py <template> <data> <output>")
        sys.exit(1)
    
    generate_html(sys.argv[1], sys.argv[2], sys.argv[3])
