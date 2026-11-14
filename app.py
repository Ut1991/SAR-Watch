"""SAR-Watch step 2: interactive demo.  Run:  streamlit run app.py"""
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="SAR-Watch", layout="wide")
st.title("SAR-Watch: Mount Rainier through the clouds")
st.write("NISAR L-band radar, July 3 vs October 31, 2026 (Track 106, Frame 25). "
         "Radar works day or night and sees through clouds.")

try:
    d = np.load("sar_watch_result.npz")
except FileNotFoundError:
    st.error("sar_watch_result.npz not found. Run sar_process.py first.")
    st.stop()

pols = [p for p in ("HHHH", "HVHV") if f"{p}_change" in d]
pol = st.sidebar.radio("Polarization", pols,
                       format_func=lambda p: {"HHHH": "HH (surface)", "HVHV": "HV (volume)"}[p])
thr = st.sidebar.slider("Change threshold (dB)", 1.0, 8.0, 3.0, 0.5)
before, after, change = d[f"{pol}_before"], d[f"{pol}_after"], d[f"{pol}_change"]
ext = [d["x"][0], d["x"][-1], d["y"][-1], d["y"][0]]

def show(img, cmap, vmin, vmax, title):
    fig, ax = plt.subplots(figsize=(6, 6))
    im = ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, extent=ext)
    ax.set_title(title); ax.axis("off"); fig.colorbar(im, ax=ax, shrink=0.7)
    return fig

tab1, tab2, tab3 = st.tabs(["Before and after", "Change map", "Radar 101"])

with tab1:
    blend = st.slider("Slide from July to October", 0.0, 1.0, 0.0, 0.05)
    mix = (1 - blend) * before + blend * after
    st.pyplot(show(mix, "gray", -25, 0, f"Backscatter (dB), {int(blend*100)}% October"))

with tab2:
    up, down = change > thr, change < -thr
    valid = np.isfinite(change).sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Area brighter", f"{100*up.sum()/valid:.1f}%")
    c2.metric("Area darker", f"{100*down.sum()/valid:.1f}%")
    c3.metric("Pixel area", f"{(abs(d['x'][1]-d['x'][0])):.0f} m")
    col1, col2 = st.columns(2)
    col1.pyplot(show(change, "RdBu_r", -6, 6, "Change (dB): red brighter, blue darker"))
    mask = np.full(change.shape, np.nan); mask[up] = 1; mask[down] = -1
    col2.pyplot(show(mask, "bwr", -1, 1, f"Changed by more than {thr} dB"))

with tab3:
    st.markdown("""
**How does radar see the ground?** NISAR sends microwave pulses (L-band, about 24 cm
wavelength) and measures how much energy bounces back. That echo is called *backscatter*.

**Why L-band?** Long waves pass through clouds, rain, and darkness, and even through dry snow
and tree canopies. Optical cameras can't.

**What makes a pixel bright or dark?**
- Rough surfaces and rocks scatter energy back: **bright**.
- Smooth or wet surfaces reflect energy away, and liquid water absorbs microwaves: **dark**.
- Forests scatter in many directions, which shows up strongly in **HV** (cross-polarization).

**What changes on Mount Rainier between July and October?**
- In summer, melting glacier surfaces are wet, so they absorb the radar signal and look dark.
- In autumn, surfaces refreeze and new dry snow is nearly transparent at L-band, so the
  signal reaches rougher ice below and comes back stronger.
- So **red** areas often mark refreezing ice and snow, and **blue** areas mark wetter or
  smoother surfaces. Field data or optical images are needed to confirm each case.

**Why the speckle?** Radar images are grainy because echoes from many tiny scatterers add up
randomly. We average neighbouring pixels (a boxcar filter) to reduce this.
""")
