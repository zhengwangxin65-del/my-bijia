#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比价监控 · 云端版
作者: 融达宝宝 ✧*。 仅供个人使用
"""

import os, re, json, time
from datetime import datetime
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
LIST_FILE = "watchlist.json"
HIST_FILE = "docs/history.json"
WEBHOOK = os.environ.get("WECHAT_WEBHOOK", "")


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get(url):
    time.sleep(2)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return r.text
    except Exception as e:
        print("  抓取失败:", e)
        return None


def search(keyword):
    out = []
    html = get(f"https://search.smzdm.com/?c=home&s={quote(keyword)}")
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for it in soup.select(".feed-block")[:8]:
            p = it.select_one(".feed-block-extras")
            if p:
                m = re.search(r"(\d+(?:\.\d+)?)", p.get_text())
                if m:
                    out.append({"site": "什么值得买", "price": float(m.group(1))})
    html = get(f"https://s.manmanbuy.com/Default.aspx?key={quote(keyword)}")
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for it in soup.select(".list-item, .item")[:8]:
            p = it.select_one(".price, .p-price")
            if p:
                m = re.search(r"(\d+(?:\.\d+)?)", p.get_text())
                if m:
                    out.append({"site": "慢慢买", "price": float(m.group(1))})
    return out


def push(text):
    if not WEBHOOK:
        print("(未配置推送，跳过)")
        return
    try:
        requests.post(WEBHOOK, json={"msgtype": "text",
                      "text": {"content": text}}, timeout=10)
        print("✅ 推送成功")
    except Exception as e:
        print("❌ 推送失败:", e)


def main():
    cfg = load(LIST_FILE, {"items": []})
    hist = load(HIST_FILE, {"updated": "", "items": []})
    by_name = {h["name"]: h for h in hist.get("items", [])}
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    alerts = []

    for it in cfg.get("items", []):
        name, target = it["name"], it.get("target", 0)
        print("▶", name)
        prices = search(name)
        if not prices:
            print("  没抓到")
            continue
        low = min(prices, key=lambda x: x["price"])
        print(f"  最低 ¥{low['price']} ({low['site']})")
        rec = by_name.get(name, {"name": name, "history": []})
        rec["target"] = target
        rec["last"] = {"low": low["price"], "site": low["site"],
                       "date": today, "all": prices}
        prev = [h["low"] for h in rec["history"]]
        rec["history"] = (rec["history"] + [
            {"date": today, "low": low["price"]}])[-90:]
        by_name[name] = rec

        if target and low["price"] <= target:
            alerts.append(f"🔥 {name} ¥{low['price']} 到心理价了（{low['site']}）")
        elif prev and low["price"] < min(prev):
            alerts.append(f"📉 {name} 降价到 ¥{low['price']}")

    hist["updated"] = today
    hist["items"] = list(by_name.values())
    save(HIST_FILE, hist)
    print(f"💾 已保存 {HIST_FILE}")
    if alerts:
        push("💰 比价提醒\n" + "\n".join(alerts))


if __name__ == "__main__":
    main()
