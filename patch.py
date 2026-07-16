import re

with open('/home/richardmelvin52/FSS/recommend_daemon/src/DbusInterface.py', 'r') as f:
    content = f.read()

content = content.replace('''                try:
                    result = self._interface_instance._generate_callback(
                        recipe_name, batch_id
                    )
                    return json.dumps(result, ensure_ascii=False)''', '''                try:
                    import asyncio
                    result = await asyncio.to_thread(
                        self._interface_instance._generate_callback,
                        recipe_name, batch_id
                    )
                    return json.dumps(result, ensure_ascii=False)''')

content = content.replace('''                try:
                    result = self._interface_instance._recipes_callback()
                    return json.dumps(result, ensure_ascii=False)''', '''                try:
                    import asyncio
                    result = await asyncio.to_thread(self._interface_instance._recipes_callback)
                    return json.dumps(result, ensure_ascii=False)''')

content = content.replace('''                try:
                    result = self._interface_instance._shopping_list_callback(
                        batch_id
                    )
                    return json.dumps(result, ensure_ascii=False)''', '''                try:
                    import asyncio
                    result = await asyncio.to_thread(self._interface_instance._shopping_list_callback, batch_id)
                    return json.dumps(result, ensure_ascii=False)''')

content = content.replace('''                try:
                    result = self._interface_instance._mark_purchased_callback(
                        item_id
                    )
                    return result''', '''                try:
                    import asyncio
                    result = await asyncio.to_thread(self._interface_instance._mark_purchased_callback, item_id)
                    return result''')

with open('/home/richardmelvin52/FSS/recommend_daemon/src/DbusInterface.py', 'w') as f:
    f.write(content)
