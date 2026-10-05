#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比价监控 · 升级版（解决 IP 被拦问题）
作者: 融达宝宝 ✧*。
策略: 京东移动版 + 百度搜索结果兜底，多重保险
"""

import os, re, json, time
from datetime import datetime
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                   "Mobile/15E148 Safari/604.1"),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.jd.com/",
}
LIST_FILE = "watchlist.json"
HIST_FILE = "docs/history.json"


def load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch(url, delay=3):
    time.sleep(delay)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as e:
        print(f"  ⚠️ 抓取失败: {url} → {e}")
        return None


def search_jd(keyword):
    """京东移动版搜索"""
    results = []
    url = f"https://so.m.jd.com/ware/search.action?keyword={quote(keyword)}&enc=utf-8"
    html = fetch(url)
    if not html:
        return results
    soup = BeautifulSoup(html, "html.parser")
    for it in soup.select(".ware-list .ware-item, .search_pro .product, li.item")[:8]:
        t = it.select_one(".ware-title, .p-name, .name, .tit")
        p = it.select_one(".ware-price, .p-price, .price")
        if t and p:
            m = re.search(r"(\d+(?:\.\d+)?)", p.get_text())
            if m:
                results.append({"site": "京东", "price": float(m.group(1)), "title": t.get_text().strip()[:30]})
    return results


def search_baidu(keyword):
    """百度搜索结果兜底（只提取商品相关内容）"""
    results = []
    url = f"https://www.baidu.com/s?wd={quote(keyword + ' 价格')}&rn=10"
    html = fetch(url)
    if not html:
        return results
    soup = BeautifulSoup(html, "html.parser")
    for it in soup.select(".c-container")[:10]:
        t = it.select_one("h3, .t, .result-title")
        p_text = it.get_text()
        # 找价格
        m = re.search(r"[¥￥]\s*(\d+(?:\.\d+)?)", p_text)
        if m and t:
            results.append({"site": "百度", "price": float(m.group(1)), "title": t.get_text().strip()[:30]})
    return results


def search(keyword):
    """多源搜索，取最低价"""
    prices = []
    print(f"  → 京东搜索...")
    prices.extend(search_jd(keyword))
    print(f"  → 百度兜底...")
    prices.extend(search_baidu(keyword))
    return prices


def main():
    cfg = load(LIST_FILE, {"items": []})
    hist = load(HIST_FILE, {"updated": "", "items": []})
    by_name = {h["name"]: h for h in hist.get("items", [])}
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    alerts = []

    for it in cfg.get("items", []):
        name, target = it["name"], it.get("target", 0)
        print(f"▶ {name}")
        all_prices = search(name)
        if not all_prices:
            print(f"  ❌ 什么都没抓到，网站可能都拦了")
            continue
        best = min(all_prices, key=lambda x: x["price"])
        print(f"  ✅ 最低 ¥{best['price']} ({best['site']})")

        rec = by_name.get(name, {"name": name, "history": []})
        rec["target"] = target
        rec["last"] = {"low": best["price"], "site": best["site"],
                       "date": today, "all": all_prices}
        prev = [h["low"] for h in rec["history"]]
        rec["history"] = (rec["history"] + [{"date": today, "low": best["price"]}])[-90:]
        by_name[name] = rec

        if target and best["price"] <= target:
            alerts.append(f"🔥 {name} ¥{best['price']} 到心理价 ¥{target}！（{best['site']}）")
        elif prev and best["price"] < min(prev):
            alerts.append(f"📉 {name} 降价到 ¥{best['price']}")

    hist["updated"] = today
    hist["items"] = list(by_name.values())
    save(HIST_FILE, hist)
    print(f"\n💾 已保存 {HIST_FILE}")
    if alerts:
        print("\n🔔 降价提醒：")
        for a in alerts:
            print(" ", a)
    else:
        print("😌 暂无降价")


if __name__ == "__main__":
    main()
