import json
from implementation import Product
outputs=[]
for data in [{}, {"count":"4"}, {"count":0}, {"count":-1}]:
    try:
        item=Product.model_validate(data)
        outputs.append({"accepted":True,"value":item.count})
    except Exception:
        outputs.append({"accepted":False})
print(json.dumps(outputs))
