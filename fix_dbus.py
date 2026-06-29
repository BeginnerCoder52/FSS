import sys

filepath = '/etc/dbus-1/system.d/vn.edu.uit.FSS.conf'
with open(filepath, 'r') as f:
    content = f.read()

# Replace the second <policy user="root"> with <policy user="richardmelvin52">
content = content.replace('<!-- FSS runtime user policy -->\n  <policy user="root">', '<!-- FSS runtime user policy -->\n  <policy user="richardmelvin52">')

with open('temp.conf', 'w') as f:
    f.write(content)
