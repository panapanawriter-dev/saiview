import streamlit as st
from supabase import create_client
from PIL import Image, ImageOps
import io
import uuid
import html
import re
from pathlib import Path
from datetime import datetime, timezone
import streamlit.components.v1 as components

st.set_page_config(page_title="SAI VIEW", page_icon="📍", layout="wide")

location_picker = components.declare_component(
    "location_picker", path=str(Path(__file__).parent / "location_picker")
)

def show_backend_error(action, error):
    """Show actionable diagnostics without exposing connection credentials."""
    code = str(getattr(error, "code", "") or "")
    message = str(getattr(error, "message", "") or str(error))
    for setting in ("SUPABASE_KEY", "SUPABASE_URL"):
        try:
            secret = str(st.secrets[setting])
            if secret:
                message = message.replace(secret, "[非表示]")
        except Exception:
            pass
    message = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[非表示]", message)
    message = re.sub(r"sb_(?:secret|publishable)_[A-Za-z0-9_-]+", "[非表示]", message)
    if code == "42501":
        guidance = "reports テーブルの権限と RLS ポリシーを確認してください。"
    elif code in ("PGRST205", "42P01"):
        guidance = "接続先に public.reports テーブルが存在するか確認してください。"
    elif code in ("PGRST204", "42703"):
        guidance = "reports の列名を確認してください。必要な列：name, damage_type, lat, lon, comment, photo_url。"
    elif any(term in message.lower() for term in ("getaddrinfo", "name resolution", "nodename", "11001")):
        guidance = "Supabase の接続先を見つけられません。プロジェクトの稼働状態と SUPABASE_URL、ネットワークを確認してください。"
    elif any(term in message.lower() for term in ("invalid api key", "invalid jwt", "unauthorized")):
        guidance = "SUPABASE_URL と SUPABASE_KEY が同じプロジェクトの設定か確認してください。"
    else:
        guidance = "下のエラー詳細を確認してください。"
    st.error(f"{action}。{guidance}")
    with st.expander(f"{action}：エラー詳細"):
        st.code(f"種類: {type(error).__name__}\nコード: {code or 'なし'}\n内容: {message[:2000]}", language=None)

# Supabase 接続
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as error:
    show_backend_error("Supabase の接続設定を読み込めませんでした", error)
    st.stop()

st.title("SAI VIEW")

# URLで入力画面と集計画面を直接開けるようにする。
initial_mode = "集計・確認" if st.query_params.get("view") == "dashboard" else "情報を登録"
mode = st.radio("画面", ["情報を登録", "集計・確認"], index=["情報を登録", "集計・確認"].index(initial_mode), horizontal=True)
st.query_params["view"] = "dashboard" if mode == "集計・確認" else "report"

if mode == "情報を登録":
    # -----------------------------
    # ① 選択位置をセッションに保持
    # -----------------------------
    lat0 = st.session_state.get("latitude", 33.5902)
    lon0 = st.session_state.get("longitude", 130.4017)

    # -----------------------------
    # ② ピンドラッグで位置補正（Leaflet）
    # -----------------------------
    st.subheader("登録する場所")
    st.caption("現在地を取得した後、ピンを指でドラッグして調整してください。地図をタップしても移動できます。")
    map_data = location_picker(lat=lat0, lon=lon0, key="report_location")

    corrected_lat = lat0
    corrected_lon = lon0

    if map_data and "lat" in map_data and "lon" in map_data:
        corrected_lat = float(map_data["lat"])
        corrected_lon = float(map_data["lon"])
        if -90 <= corrected_lat <= 90 and -180 <= corrected_lon <= 180:
            st.session_state["latitude"] = corrected_lat
            st.session_state["longitude"] = corrected_lon
            st.session_state["location_selected"] = True

    if st.session_state.get("location_selected"):
        st.caption(f"登録位置：{corrected_lat:.6f}, {corrected_lon:.6f}")

    # -----------------------------
    # ③ 入力フォーム
    # -----------------------------
    with st.form("report_form"):
        name = st.text_input("名前")
        damage_type = st.selectbox("被害種別", ["倒木", "冠水", "停電", "その他"])

        st.caption(f"保存する位置：{corrected_lat:.6f}, {corrected_lon:.6f}")

        comment = st.text_area("コメント")
        uploaded_file = st.file_uploader("現場写真をアップロード", type=["jpg", "jpeg", "png"])

        submitted = st.form_submit_button("この地点の情報を保存", use_container_width=True)

    # -----------------------------
    # ④ Supabase に保存
    # -----------------------------
    if submitted:
        if not st.session_state.get("location_selected"):
            st.warning("現在地を取得するか、地図をタップして登録する場所を選んでください。")
            st.stop()
        lat, lon = st.session_state["latitude"], st.session_state["longitude"]
        photo_url = None

        try:
            if uploaded_file is not None:
                img = ImageOps.exif_transpose(Image.open(uploaded_file)).convert("RGB")
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
        except Exception as error:
            show_backend_error("写真を保存できませんでした", error)
            st.stop()

        data = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "damage_type": damage_type,
            "lat": lat,
            "lon": lon,
            "comment": comment,
            "photo_url": photo_url
        }

        try:
            supabase.table("reports").insert(data).execute()
            st.success("選択した地点に保存しました！")
        except Exception as error:
            show_backend_error("保存できませんでした", error)
            st.caption("入力は保持されています。原因を解消してから再送信してください。")

    st.stop()  # 入力画面では集計データやPC用の地図を読み込まない。

# -----------------------------
# ⑤ pydeck で災害報告マップ表示（元コード維持）
# -----------------------------
import pandas as pd
import pydeck as pdk

st.header("報告の集計・確認")
st.caption("スマホで保存された報告を地図と一覧で確認できます。表示データは最大30秒間キャッシュします。")

@st.cache_data(ttl=30, show_spinner=False)
def load_reports():
    rows = []
    offset = 0
    while True:
        page = (supabase.table("reports")
                .select("name,damage_type,lat,lon,comment,photo_url,created_at")
                .order("created_at", desc=True)
                .order("lat").order("lon").order("name").order("comment")
                .range(offset, offset + 499).execute()).data or []
        rows.extend(page)
        if not page:
            return rows
        offset += len(page)

if st.button("最新の情報に更新"):
    load_reports.clear()


try:
    rows = load_reports()
except Exception as error:
    show_backend_error("報告を読み込めませんでした", error)
    st.stop()
df = pd.DataFrame(rows, columns=["lat", "lon", "damage_type", "comment", "photo_url", "name", "created_at"])
df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
df = df.sort_values("created_at", ascending=False, na_position="last", kind="stable")
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
valid_positions = df["lat"].between(-90, 90) & df["lon"].between(-180, 180)
if df.empty:
    st.info("まだ登録された報告はありません。")
    st.stop()

metrics = st.columns(5)
metrics[0].metric("報告総数", len(df))
for column, category in zip(metrics[1:], ["倒木", "冠水", "停電", "その他"]):
    column.metric(category, int((df["damage_type"] == category).sum()))

selected_types = st.multiselect("地図・一覧に表示する被害種別", ["倒木", "冠水", "停電", "その他"], default=["倒木", "冠水", "停電", "その他"])
keyword = st.text_input("名前・コメントで検索", placeholder="例：道路、交差点、報告者の名前")
filtered = df[df["damage_type"].isin(selected_types)].copy()
if keyword:
    filtered = filtered[filtered["name"].fillna("").str.contains(keyword, regex=False, case=False) | filtered["comment"].fillna("").str.contains(keyword, regex=False, case=False)]
st.caption(f"表示対象：{len(filtered)}件 ／ 全{len(df)}件")
st.subheader("報告一覧")
display_df = filtered.rename(columns={"name": "報告者", "damage_type": "被害種別", "comment": "コメント", "lat": "緯度", "lon": "経度", "photo_url": "写真"})
st.dataframe(display_df[["被害種別", "報告者", "コメント", "写真", "緯度", "経度"]], hide_index=True, use_container_width=True, column_config={"写真": st.column_config.LinkColumn("写真", display_text="写真を開く")})
st.download_button("表示中の一覧をCSVでダウンロード", display_df.to_csv(index=False).encode("utf-8-sig"), file_name="reports.csv", mime="text/csv")

df = filtered.loc[valid_positions.reindex(filtered.index)].copy()
st.subheader("報告マップ")
if df.empty:
    st.info("表示対象に地図へ表示できる報告がありません。")
    st.stop()

color_map = {
    "倒木": [0, 128, 0],
    "冠水": [0, 0, 255],
    "停電": [255, 255, 0],
    "その他": [255, 0, 0],
}
df["color"] = df["damage_type"].apply(lambda x: color_map.get(x, [255, 0, 0]))

def make_tooltip(row):
    tooltip_html = f"<b>{html.escape(str(row['damage_type']))}</b><br>{html.escape(str(row['comment']))}<br>"
    photo_url = row.get("photo_url")

    if isinstance(photo_url, str) and photo_url.startswith("http"):
        tooltip_html += f"<img src='{html.escape(photo_url, quote=True)}' width='150' style='border-radius:8px'><br>"

    tooltip_html += f"<i>報告者: {html.escape(str(row['name']))}</i>"
    return tooltip_html

df["tooltip_html"] = df.apply(make_tooltip, axis=1)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position='[lon, lat]',
    get_fill_color='color',
    get_radius=30,
    radius_min_pixels=4,
    radius_max_pixels=50,
    pickable=True,
)

tooltip = {
    "html": "{tooltip_html}",
    "style": {"backgroundColor": "white", "color": "black"}
}

latest_report = df.iloc[0]
view_state = pdk.ViewState(
    latitude=float(latest_report["lat"]),
    longitude=float(latest_report["lon"]),
    zoom=12,
    min_zoom=1,
    max_zoom=18
)

st.pydeck_chart(pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style="light"
))
