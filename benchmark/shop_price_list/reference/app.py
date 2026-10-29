# Reference backend for shop_price_list: proves the hidden tests are right.
# Deliberately uses different names (product, cedis, section, /shop/products) to exercise ops.json translation.
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
products = {}
next_id = 1


class ProductIn(BaseModel):
    product: str
    cedis: float = Field(gt=0)
    section: str


class PriceIn(BaseModel):
    cedis: float = Field(gt=0)


def find(product_id):
    if product_id not in products:
        raise HTTPException(404, "No such item")
    return products[product_id]


@app.post("/shop/products", status_code=201)
def add_item(p: ProductIn):
    global next_id
    if any(x["product"].lower() == p.product.lower() for x in products.values()):
        raise HTTPException(409, "An item with this name already exists")
    item = {"id": next_id, **p.model_dump()}
    products[next_id] = item
    next_id += 1
    return item


@app.get("/shop/products")
def list_items(section: str | None = None):
    return [p for p in products.values() if section is None or p["section"] == section]


@app.get("/shop/products/{product_id}")
def get_item(product_id: int):
    return find(product_id)


@app.patch("/shop/products/{product_id}")
def change_price(product_id: int, p: PriceIn):
    item = find(product_id)
    item["cedis"] = p.cedis
    return item


@app.delete("/shop/products/{product_id}", status_code=204)
def remove_item(product_id: int):
    find(product_id)
    del products[product_id]
