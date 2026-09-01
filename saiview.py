import streamlit as st
from streamlit_js_eval import streamlit_js_eval
from supabase import create_client
import pandas as pd
import pydeck as pdk
from PIL import Image
import io
import uuid

# ---------------------------------------------------------
# 🔗 Supabase 接続
# ---------------------------------------------------------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.title("SAI VIEW")

# ---------------------------------------------------------
# 📱 スマホの現在地を取得（streamlit-js-eval）
# ---------------------------------------------------------
location = streamlit_js_eval(
    js_expressions="navigator.geolocation.getCurrentPosition((pos)=>pos.coords)"
)

if location:
    st.session_state["lat"] = location["latitude"]
    st.session_state["lon"] = location["longitude"]

# 初期化
if "lat" not in st.session_state:
    st.session_state["lat"] = 0.0
if "lon" not in st.session_state:
    st.session_state["lon"] = 0.0

# ---------------------------------------------------------
# 📍 緯度・経度入力欄（自動反映＋手動補正）
# ---------------------------------------------------------
st.subheader("位置情報（自動取得＋手動補正）")

lat = st.number_input(
    "緯度（latitude）",
    value=st.session_state["lat"],
    format="%.6f"
)
lon = st.number_input(
    "経度（longitude）",
    value=st.session_state["lon"],
    format="%.6f"
)

st.caption("※ 現在地がズレていたら数値を手動で補正してください")

# ---------------------------------------------------------
# 📝 入力フォーム
# ---------------------------------------------------------
with st.form("report_form"):
    name = st.text_input("名前")
    damage_type = st.selectbox("被害種別", ["倒木", "冠水", "停電", "その他"])
    comment = st.text_area("コメント")
    uploaded_file = st.file_uploader("現場写真をアップロード", type=["jpg", "jpeg", "png"])

    submitted = st.form_submit_button("送信")

# ---------------------------------------------------------
# 📤 Supabase に保存
# ---------------------------------------------------------
if submitted:
    photo_url = None

    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        img.thumbnail((800, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)

        file_name = f"{uuid.uuid4()}.jpg"
        supabase.storage.from_("reports").upload(
            file_name,
            buffer.read(),
            {"content-type": "image/jpeg"}
        )
        photo_url = supabase.storage.from_("reports").get_public_url(file_name)

    data = {
        "name": name,
        "damage_type": damage_type,
        "lat": lat,
        "lon": lon,
        "comment": comment,
        "photo_url": photo_url
    }

    supabase.table("reports").insert(data).execute()
    st.success("送信しました！")

# ---------------------------------------------------------
# 🗺 地図表示
# ---------------------------------------------------------
st.header("災害報告マップ")

res = supabase.table("reports").select("*").execute()
df = pd.DataFrame(res.data)
df = df.dropna(subset=["lat", "lon"])

color_map = {
    "倒木": [0, 128, 0],
    "冠水": [0, 0, 255],
    "停電": [255, 255, 0],
    "その他": [255, 0, 0],
}
df["color"] = df["damage_type"].apply(lambda x: color_map.get(x, [255, 0, 0]))

def make_tooltip(row):
    html = f"<b>{row['damage_type']}</b><br>{row['comment']}<br>"
    if isinstance(row.get("photo_url"), str):
        html += f"<img src='{row['photo_url']}' width='150'><br>"
    html += f"<i>報告者: {row['name']}</i>"

