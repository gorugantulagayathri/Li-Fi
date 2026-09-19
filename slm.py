"""
Spatial Light Modulator (SLM) Inspired Phase Mask & Far-Field Diffraction Model.
Computes 2D phase gradient masks and 2D FFT far-field beam steering profiles.
"""

import math
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Tuple, Dict, Any
from config import SLM_GRID_SIZE, OPTICAL_WAVELENGTH_NM

class SLMPhaseMaskModel:
    def __init__(self, grid_size: int = SLM_GRID_SIZE, wavelength_nm: float = OPTICAL_WAVELENGTH_NM):
        self.grid_size = grid_size
        self.wavelength_m = wavelength_nm * 1e-9

    def calculate_phase_mask(self, azimuth_rad: float, elevation_deg: float = 15.0) -> np.ndarray:
        """
        Generates 2D SLM phase mask array phi(x,y) wrapped in [0, 2*pi].
        phi(x,y) = mod((2*pi / lambda) * (x * sin(theta_x) + y * sin(theta_y)), 2*pi)
        """
        elev_rad = math.radians(elevation_deg)
        theta_x = math.cos(azimuth_rad) * math.sin(elev_rad)
        theta_y = math.sin(azimuth_rad) * math.sin(elev_rad)

        # Spatial coordinates grid [-1, 1]
        x = np.linspace(-1.0, 1.0, self.grid_size)
        y = np.linspace(-1.0, 1.0, self.grid_size)
        X, Y = np.meshgrid(x, y)

        # Phase gradient phase ramp factor
        k_factor = (2.0 * np.pi / 0.05)  # Spatial frequency factor
        phase = k_factor * (X * theta_x + Y * theta_y)

        # Wrap phase to [0, 2*pi]
        phase_mask = np.mod(phase, 2.0 * np.pi)
        return phase_mask

    def calculate_far_field_diffraction(self, phase_mask: np.ndarray) -> np.ndarray:
        """
        Computes 2D FFT of complex optical wavefront E(x,y) = exp(i * phi(x,y))
        to visualize the far-field optical intensity spot steered by the SLM.
        """
        complex_field = np.exp(1j * phase_mask)
        # 2D FFT shift to center far-field beam spot
        fft_field = np.fft.fftshift(np.fft.fft2(complex_field))
        far_field_intensity = np.abs(fft_field) ** 2
        
        # Logarithmic scaling for visual clarity of side lobes
        far_field_intensity = np.log1p(far_field_intensity)
        # Normalize to [0, 1]
        max_val = np.max(far_field_intensity)
        if max_val > 0:
            far_field_intensity /= max_val

        return far_field_intensity

    def get_phase_mask_fig(self, phase_mask: np.ndarray, title: str = "SLM Phase Mask (0 to 2π)") -> go.Figure:
        """Generates Plotly heatmap for 2D Phase Mask."""
        fig = px.imshow(
            phase_mask,
            color_continuous_scale="Viridis",
            labels=dict(x="SLM Pixels (X)", y="SLM Pixels (Y)", color="Phase (rad)"),
            title=title
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=40, b=10),
            height=300,
            coloraxis_colorbar=dict(title="rad", tickvals=[0, np.pi, 2*np.pi], ticktext=["0", "π", "2π"])
        )
        return fig

    def get_far_field_fig(self, far_field_intensity: np.ndarray, title: str = "FFT Far-Field Diffraction Pattern") -> go.Figure:
        """Generates Plotly heatmap for 2D Far-Field Intensity Profile."""
        fig = px.imshow(
            far_field_intensity,
            color_continuous_scale="Plasma",
            labels=dict(x="Angle X", y="Angle Y", color="Intensity"),
            title=title
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=40, b=10),
            height=300
        )
        return fig
