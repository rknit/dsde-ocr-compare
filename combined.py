import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
KAN = ROOT / "kan-result"
AOMSIN = ROOT / "aomsin-result"

st.set_page_config(page_title="OCR Comparison — Kan vs Aomsin", layout="wide")


# ── Data loading ───────────────────────────────────────────────────────────────


@st.cache_data
def load_kan():
    return _load_from(KAN)


@st.cache_data
def load_aomsin():
    return _load_from(AOMSIN)


def _load_from(base: Path):
    ocr_cand = json.loads(
        (base / "ocr_candidate_result.json").read_text(encoding="utf-8")
    )
    ref_cand = json.loads(
        (base / "ref_candidate_result.json").read_text(encoding="utf-8")
    )
    ocr_party = json.loads((base / "ocr_party_result.json").read_text(encoding="utf-8"))
    ref_party = json.loads((base / "ref_party_result.json").read_text(encoding="utf-8"))
    cand_map = json.loads(
        (base / "maps" / "candidate_map.json").read_text(encoding="utf-8")
    )
    party_map = json.loads(
        (base / "maps" / "party_map.json").read_text(encoding="utf-8")
    )
    return ocr_cand, ref_cand, ocr_party, ref_party, cand_map, party_map


# ── Helpers ────────────────────────────────────────────────────────────────────


def pct_error(ocr, ref):
    if ref == 0:
        return float("inf") if ocr != 0 else 0.0
    return abs(ocr - ref) / ref * 100


def _error_color(err):
    if err < 1:
        return "#2ca02c"
    if err < 5:
        return "#ff7f0e"
    return "#d62728"


def build_candidate_df(ocr_cand, ref_cand, cand_map):
    all_ids = sorted(set(list(ocr_cand.keys()) + list(ref_cand.keys())), key=int)
    rows = []
    for cid in all_ids:
        name = cand_map.get(cid, {}).get("ชื่อ_สกุล", f"#{cid}")
        party = cand_map.get(cid, {}).get("พรรค", "")
        ocr = ocr_cand[cid]["vote"] if cid in ocr_cand else 0
        ref = ref_cand[cid]["vote"] if cid in ref_cand else 0
        err = pct_error(ocr, ref)
        rows.append(
            {
                "#": cid,
                "label": f"#{cid} {name}",
                "Candidate": name,
                "Party": party,
                "OCR": ocr,
                "Ref": ref,
                "Diff": ocr - ref,
                "Error %": round(err, 2),
                "phantom": False,
            }
        )
    return pd.DataFrame(rows)


def build_party_df(ocr_party, ref_party, party_map):
    all_ids = sorted(set(list(ocr_party.keys()) + list(ref_party.keys())), key=int)
    rows = []
    for pid in all_ids:
        name = party_map.get(pid, f"พรรค {pid}")
        ocr = ocr_party.get(pid, 0)
        ref = ref_party.get(pid, 0)
        phantom = pid not in ref_party
        err = pct_error(ocr, ref)
        rows.append(
            {
                "#": pid,
                "label": f"#{pid} {name}",
                "Party": name,
                "OCR": ocr,
                "Ref": ref,
                "Diff": ocr - ref,
                "Error %": round(err, 2) if not phantom else None,
                "phantom": phantom,
            }
        )
    return pd.DataFrame(rows)


def _grouped_bar_fig(normal, phantoms, title):
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="OCR",
            x=normal["label"],
            y=normal["OCR"],
            marker_color="#4C78A8",
            customdata=normal[["Ref", "Diff", "Error %"]].values,
            hovertemplate=(
                "<b>%{x}</b><br>OCR: %{y:,}<br>Ref: %{customdata[0]:,}<br>"
                "Diff: %{customdata[1]:+,}<br>Error: %{customdata[2]:.2f}%<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            name="Reference",
            x=normal["label"],
            y=normal["Ref"],
            marker_color="#F58518",
            customdata=normal[["OCR", "Diff", "Error %"]].values,
            hovertemplate=(
                "<b>%{x}</b><br>Ref: %{y:,}<br>OCR: %{customdata[0]:,}<br>"
                "Diff: %{customdata[1]:+,}<br>Error: %{customdata[2]:.2f}%<extra></extra>"
            ),
        )
    )
    if not phantoms.empty:
        fig.add_trace(
            go.Bar(
                name="OCR (phantom — no ref)",
                x=phantoms["label"],
                y=phantoms["OCR"],
                marker_color="#E45756",
                hovertemplate="<b>%{x}</b><br>OCR: %{y:,}<br>⚠️ No reference entry<extra></extra>",
            )
        )
    fig.update_layout(
        title=title,
        barmode="group",
        xaxis_tickangle=-40,
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest",
        margin=dict(b=100),
    )
    return fig


def grouped_bar_chart(df, title):
    return _grouped_bar_fig(df[~df["phantom"]], df[df["phantom"]], title)


def votes_bar_chart(df, title):
    normal = df[~df["phantom"]].sort_values("Ref", ascending=False)
    return _grouped_bar_fig(normal, df[df["phantom"]], title)


def error_bar_chart(df, title):
    data = df[~df["phantom"] & df["Error %"].notna()].copy()
    data = data.sort_values("Error %", ascending=True).reset_index(drop=True)
    colors = [_error_color(e) for e in data["Error %"]]
    fig = go.Figure(
        go.Bar(
            x=data["Error %"],
            y=data["label"],
            orientation="h",
            marker_color=colors,
            customdata=data[["OCR", "Ref", "Diff"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>Error: %{x:.2f}%<br>OCR: %{customdata[0]:,}<br>"
                "Ref: %{customdata[1]:,}<br>Diff: %{customdata[2]:+,}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="% Error  |OCR − Ref| / Ref × 100",
        height=max(300, len(data) * 20 + 80),
        shapes=[
            dict(
                type="line",
                x0=1,
                x1=1,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(color="#ff7f0e", dash="dash", width=1.5),
            ),
            dict(
                type="line",
                x0=5,
                x1=5,
                y0=0,
                y1=1,
                yref="paper",
                line=dict(color="#d62728", dash="dash", width=1.5),
            ),
        ],
        annotations=[
            dict(
                x=1,
                y=1,
                yref="paper",
                text="1%",
                showarrow=False,
                font=dict(color="#ff7f0e", size=11),
                xanchor="left",
                yanchor="bottom",
            ),
            dict(
                x=5,
                y=1,
                yref="paper",
                text="5%",
                showarrow=False,
                font=dict(color="#d62728", size=11),
                xanchor="left",
                yanchor="bottom",
            ),
        ],
        margin=dict(l=20),
    )
    return fig


def metrics_row(df, label):
    valid = df[~df["phantom"] & df["Error %"].notna()]
    total_ocr = int(df["OCR"].sum())
    total_ref = int(df["Ref"].sum())
    total_diff = total_ocr - total_ref
    total_err = pct_error(total_ocr, total_ref)
    weighted_mean_err = valid["Diff"].abs().sum() / valid["Ref"].sum() * 100
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total OCR Votes", f"{total_ocr:,}")
    c2.metric(
        "Total Ref Votes", f"{total_ref:,}", delta=f"{total_diff:+,}", delta_color="off"
    )
    c3.metric("Total Vote Error %", f"{total_err:.2f}%")
    c4.metric(f"Weighted Mean Error per {label}", f"{weighted_mean_err:.2f}%")


def render_dataset_tab(ocr_cand, ref_cand, ocr_party, ref_party, cand_map, party_map):
    cand_df = build_candidate_df(ocr_cand, ref_cand, cand_map)
    party_df = build_party_df(ocr_party, ref_party, party_map)

    sub_cand, sub_party = st.tabs(["🧑 Candidates", "🏛 Parties"])

    with sub_cand:
        st.subheader("Candidate Summary")
        metrics_row(cand_df, "Candidate")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                grouped_bar_chart(cand_df, "Candidate Votes: by ID"),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                votes_bar_chart(cand_df, "Candidate Votes: by Vote Count"),
                use_container_width=True,
            )
        st.plotly_chart(
            error_bar_chart(cand_df, "Candidate % Error"), use_container_width=True
        )
        with st.expander("Data Table"):
            st.dataframe(
                cand_df[["#", "Candidate", "Party", "OCR", "Ref", "Diff", "Error %"]],
                use_container_width=True,
                hide_index=True,
            )

    with sub_party:
        phantoms = party_df[party_df["phantom"]]
        if not phantoms.empty:
            names = ", ".join(f"#{r['#']} {r['Party']}" for _, r in phantoms.iterrows())
            st.warning(
                f"⚠️ Phantom OCR entr{'y' if len(phantoms) == 1 else 'ies'} (in OCR but not in reference): "
                f"**{names}**. Likely an OCR misread — excluded from error stats."
            )
        st.subheader("Party Summary")
        metrics_row(party_df[~party_df["phantom"]], "Party")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                grouped_bar_chart(party_df, "Party Votes: by ID"),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                votes_bar_chart(party_df, "Party Votes: by Vote Count"),
                use_container_width=True,
            )
        st.plotly_chart(
            error_bar_chart(party_df, "Party % Error"), use_container_width=True
        )
        with st.expander("Data Table"):
            display = party_df[
                ["#", "Party", "OCR", "Ref", "Diff", "Error %", "phantom"]
            ].copy()
            display.columns = [
                "#",
                "Party",
                "OCR",
                "Ref",
                "Diff",
                "Error %",
                "Phantom ⚠️",
            ]

            def _highlight_phantom(row):
                return (
                    ["background-color: #ffe0e0"] * len(row)
                    if row["Phantom ⚠️"]
                    else [""] * len(row)
                )

            st.dataframe(
                display.style.apply(_highlight_phantom, axis=1),
                use_container_width=True,
                hide_index=True,
            )

    return cand_df, party_df


# ── App ────────────────────────────────────────────────────────────────────────

st.title("OCR vs Reference Vote Comparison — Kan & Aomsin")
st.caption(
    "Comparing aggregated OCR results against ground-truth reference data. Error = |OCR − Ref| / Ref × 100%."
)

tab_kan, tab_aomsin, tab_compare = st.tabs(["📁 Kan", "📁 Aomsin", "⚖️ Comparison"])

with tab_kan:
    kan_cand_df, kan_party_df = render_dataset_tab(*load_kan())

with tab_aomsin:
    aom_cand_df, aom_party_df = render_dataset_tab(*load_aomsin())

# ── Comparison tab ─────────────────────────────────────────────────────────────
with tab_compare:
    st.subheader("Accuracy Comparison: Kan vs Aomsin")
    st.caption("Lower error = more accurate OCR.")

    def _summary(cand_df, party_df):
        cand_valid = cand_df[~cand_df["phantom"] & cand_df["Error %"].notna()]
        party_valid = party_df[~party_df["phantom"] & party_df["Error %"].notna()]
        return {
            "cand_total_err": pct_error(
                int(cand_df["OCR"].sum()), int(cand_df["Ref"].sum())
            ),
            "cand_mean_err": cand_valid["Diff"].abs().sum()
            / cand_valid["Ref"].sum()
            * 100,
            "party_total_err": pct_error(
                int(party_df[~party_df["phantom"]]["OCR"].sum()),
                int(party_df[~party_df["phantom"]]["Ref"].sum()),
            ),
            "party_mean_err": party_valid["Diff"].abs().sum()
            / party_valid["Ref"].sum()
            * 100,
        }

    kan_s = _summary(kan_cand_df, kan_party_df)
    aom_s = _summary(aom_cand_df, aom_party_df)

    col_kan, col_aom = st.columns(2)

    for col, s, name in [(col_kan, kan_s, "Kan"), (col_aom, aom_s, "Aomsin")]:
        with col:
            st.markdown(f"### {name}")
            m1, m2 = st.columns(2)
            m1.metric("Candidate Total Error %", f"{s['cand_total_err']:.2f}%")
            m2.metric("Candidate Weighted Mean Error %", f"{s['cand_mean_err']:.2f}%")
            m3, m4 = st.columns(2)
            m3.metric("Party Total Error %", f"{s['party_total_err']:.2f}%")
            m4.metric("Party Weighted Mean Error %", f"{s['party_mean_err']:.2f}%")

    st.divider()

    metrics_labels = [
        "Candidate Weighted Mean Error %",
        "Candidate Total Error %",
        "Party Weighted Mean Error %",
        "Party Total Error %",
    ]
    kan_vals = [
        kan_s["cand_mean_err"],
        kan_s["cand_total_err"],
        kan_s["party_mean_err"],
        kan_s["party_total_err"],
    ]
    aom_vals = [
        aom_s["cand_mean_err"],
        aom_s["cand_total_err"],
        aom_s["party_mean_err"],
        aom_s["party_total_err"],
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Kan",
            x=metrics_labels,
            y=kan_vals,
            marker_color="#4C78A8",
            text=[f"{v:.2f}%" for v in kan_vals],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Aomsin",
            x=metrics_labels,
            y=aom_vals,
            marker_color="#F58518",
            text=[f"{v:.2f}%" for v in aom_vals],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Error Metrics: Kan vs Aomsin",
        barmode="group",
        yaxis_title="% Error",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    overall_kan = (kan_s["cand_mean_err"] + kan_s["party_mean_err"]) / 2
    overall_aom = (aom_s["cand_mean_err"] + aom_s["party_mean_err"]) / 2
    if overall_kan < overall_aom:
        winner, loser, diff = "Kan", "Aomsin", overall_aom - overall_kan
        st.success(
            f"**{winner}** is more accurate overall — {diff:.2f} percentage points lower mean error than {loser} "
            f"(averaged weighted mean error across candidates and parties)."
        )
    elif overall_aom < overall_kan:
        winner, loser, diff = "Aomsin", "Kan", overall_kan - overall_aom
        st.success(
            f"**{winner}** is more accurate overall — {diff:.2f} percentage points lower mean error than {loser} "
            f"(averaged weighted mean error across candidates and parties)."
        )
    else:
        st.info("Both datasets have identical mean error rates.")
