import numpy as np
import matplotlib.pyplot as plt


class HagedornBrown:
    """
    Calculates multiphase flow pressure gradients and VLP curves for vertical wellbores
    using the Hagedorn-Brown correlation and a coupled Black Oil PVT model.
    Includes Griffith-Wallis bubble flow detection and holdup correction.
    """

    def __init__(self, tubing_id, tubing_od, casing_id, roughness, pvt_model,
                 fluid_properties, watercut=0.0, theta=0.0):
        self.tid      = tubing_id #ft
        self.tod      = tubing_od #ft
        self.cid      = casing_id #ft
        self.roughness = roughness #
        self.pvt_model = pvt_model
        self.wc       = watercut
        self.wor      = watercut / (1.0 - watercut + 1e-9)
        self.theta    = np.radians(theta)
        self.Ap       = (np.pi / 4.0) * self.tid**2
        self.Pb       = pvt_model.calc_bubble_point
        self.fp       = fluid_properties

    # ------------------------------------------------------------------
    # Fluid property update
    # ------------------------------------------------------------------

    def update_fluid_properties(self, P, T, Ql):
        self.Ql = Ql
        self.fp = self.pvt_model.fluid_properties_dict(
            P, T, self.fp["Rsb"], self.fp["Pb"]
        )

    # ------------------------------------------------------------------
    # Hagedorn-Brown dimensionless groups
    # ------------------------------------------------------------------

    def dimensionless_numbers(self):
        """
        Calculates the required Hagedorn-Brown dimensionless groups and
        sets Vsl, Vsg, Vm in self.fp.

        Returns:
            tuple: Nl, CNl, Nlv, Ngv, Nd (all dimensionless).
        """
        fo = 1.0 / (1.0 + self.wor)
        fw = self.wor  / (1.0 + self.wor)

        # In-situ liquid volumetric rate  [ft³/day]
        q_liquid_insitu = 5.615 * self.Ql * (self.fp["Bo"] * fo + self.fp["Bw"] * fw)
        self.fp["Vsl"]  = q_liquid_insitu / (86400.0 * self.Ap)

        # ----------------------------------------------------------------
        # BUG FIX — free gas calculation
        # ----------------------------------------------------------------
        # fp["glr"] must be the TOTAL surface producing GLR (scf / STB liquid),
        # derived from Rsb (initial GOR), NOT from Rs (dissolved GOR at local P).
        #
        # The PVT dict previously stored glr = Rs/(1+wor), which equals gor*fo
        # at every pressure, making free_gas_scf = Ql*(glr - gor*fo) = 0 always.
        # With Vsg = 0 there is no gas phase: holdup = 1, mixture density =
        # liquid density at every rate, and the only gradient that changes with
        # rate is friction (∝ Vm²). That produces the monotonically-increasing
        # Pwf curve seen in the plot — the U-shape requires gas gravity relief
        # to dominate at low rates, which only appears when free gas is non-zero.
        #
        # Fix applied in BlackOilPVT.fluid_properties_dict:
        #   "glr": Rsb / (1 + wor)   ← total surface GLR, constant with P
        #   "gor": Rs                 ← dissolved portion, decreases below Pb
        # Now below bubble point:  glr > gor*fo  =>  free_gas_scf > 0  ✓
        # ----------------------------------------------------------------
        free_gas_scf   = max(0.0, self.Ql * (self.fp["glr"] - self.fp["gor"] * fo))
        q_gas_insitu   = (free_gas_scf
                          * (14.7 / self.fp["Pr"])
                          * ((self.fp["Tr"] + 460.0) / 520.0)
                          * self.fp["Z"])
        self.fp["Vsg"] = q_gas_insitu / (86400.0 * self.Ap)
        self.fp["Vm"]  = self.fp["Vsl"] + self.fp["Vsg"]

        # H-B dimensionless groups
        base_term = 1.0 / (self.fp["rho_l"] * self.fp["sigma_l"] ** 3)
        Nl  = 0.15726 * self.fp["mu_l"] * (base_term ** 0.25)
        CNl = 0.061 * Nl**3 - 0.0929 * Nl**2 + 0.0505 * Nl + 0.0019

        Nlv = 1.938 * self.fp["Vsl"] * (self.fp["rho_l"] / self.fp["sigma_l"]) ** 0.25
        Ngv = 1.938 * self.fp["Vsg"] * (self.fp["rho_l"] / self.fp["sigma_l"]) ** 0.25
        Nd  = 120.872 * self.tid     * (self.fp["rho_l"] / self.fp["sigma_l"]) ** 0.5

        return Nl, CNl, Nlv, Ngv, Nd

    # ------------------------------------------------------------------
    # Bubble-flow regime detection  (Griffith & Wallis, 1961)
    # ------------------------------------------------------------------

    def is_bubble_flow(self):
        """
        Determines whether the current flow conditions fall in the bubble-flow
        regime using the Griffith-Wallis criterion.

        Bubble flow exists when the in-situ gas void fraction (λg = Vsg/Vm)
        is less than the boundary value LB:
            LB = max(0.25,  1.071 − 0.2218 · Vm² / d)

        Velocities must be computed by dimensionless_numbers() before calling
        this method (they are stored in self.fp).

        Returns:
            bool: True if bubble flow, False otherwise.
        """
        Vm  = self.fp.get("Vm",  0.0)
        Vsg = self.fp.get("Vsg", 0.0)

        if Vm <= 1e-9:
            return False

        # Griffith-Wallis bubble-flow boundary
        LB = 1.071 - 0.2218 * (Vm ** 2) / self.tid
        LB = max(LB, 0.25)

        lambda_g = Vsg / Vm          # in-situ gas void fraction (no-slip)
        return lambda_g < LB

    # ------------------------------------------------------------------
    # Griffith holdup for bubble flow
    # ------------------------------------------------------------------

    def griffith_holdup(self):
        """
        Calculates liquid holdup for bubble-flow regime using the
        Griffith-Wallis correlation and updates mixture properties in self.fp.

        The bubble-rise velocity Vs = 0.8 ft/s is a standard field-unit
        constant for oil–gas systems.

        Quadratic form (Griffith & Wallis):
            Vs·Hl² − (Vm + Vs)·Hl + Vsl = 0
        Solved directly:
            Hl = 1 − ½·[1 + Vm/Vs − √((1 + Vm/Vs)² − 4·Vsg/Vs)]

        Returns:
            float: Liquid holdup (0.0 – 1.0).
        """
        Vm  = self.fp["Vm"]
        Vsg = self.fp["Vsg"]
        Vs  = 0.8   # bubble rise velocity, ft/s

        discriminant = (1.0 + Vm / Vs) ** 2 - 4.0 * Vsg / Vs
        # Discriminant is always ≥ 0 inside bubble-flow region (λg < LB ≤ 0.25)
        discriminant = max(discriminant, 0.0)

        Hl = 1.0 - 0.5 * (1.0 + Vm / Vs - np.sqrt(discriminant))
        Hl = max(0.0, min(Hl, 1.0))

        self.fp["rho_m"] = self.fp["rho_l"] * Hl + self.fp["rho_g"] * (1.0 - Hl)
        self.fp["mu_m"]  = (self.fp["mu_l"] ** Hl) * (self.fp["mu_g"] ** (1.0 - Hl))

        return Hl

    # ------------------------------------------------------------------
    # Hagedorn-Brown holdup (slug / transition / mist)
    # ------------------------------------------------------------------

    def liquid_holdup(self):
        """
        Calculates liquid holdup using the Hagedorn-Brown correlation.
        Also sets rho_m and mu_m in self.fp.

        Returns:
            float: Liquid holdup (0.0 – 1.0).
        """
        Nl, CNl, Nlv, Ngv, Nd = self.dimensionless_numbers()
        Ngv_safe = max(Ngv, 1e-6)

        H = ((Nlv / (Ngv_safe ** 0.575))
             * (self.fp["Pr"] / 14.7) ** 0.1
             * (CNl / Nd))

        Hl_psi = np.sqrt(
            (0.0047 + 1123.32 * H + 729489.64 * H ** 2)
            / (1.0 + 1097.1566 * H + 722153.97 * H ** 2)
        )

        B = Ngv * (Nlv ** 0.38) / (Nd ** 2.14)
        if B <= 0.025:
            psi = 27170 * B**3 - 317.52 * B**2 + 0.5472 * B + 0.9999
        elif B <= 0.055:
            psi = -533.33 * B**2 + 58.524 * B + 0.1171
        else:
            psi = 2.5714 * B + 1.5962

        Hl = max(0.0, min(Hl_psi * psi, 1.0))

        self.fp["rho_m"] = self.fp["rho_l"] * Hl + self.fp["rho_g"] * (1.0 - Hl)
        self.fp["mu_m"]  = (self.fp["mu_l"] ** Hl) * (self.fp["mu_g"] ** (1.0 - Hl))

        return Hl

    # ------------------------------------------------------------------
    # Combined holdup dispatcher
    # ------------------------------------------------------------------

    def get_holdup(self):
        """
        Routes to the correct holdup correlation based on flow regime.

        Calls dimensionless_numbers() first so that Vm / Vsg are current,
        then checks for bubble flow. Returns Hl from whichever method applies.

        Returns:
            float: Liquid holdup (0.0 – 1.0).
        """
        # dimensionless_numbers() populates Vsl, Vsg, Vm — required by is_bubble_flow()
        # liquid_holdup() calls dimensionless_numbers() again internally, but
        # self.fp velocities are already set so the second call is consistent.
        self.dimensionless_numbers()

        if self.is_bubble_flow():
            return self.griffith_holdup()
        else:
            return self.liquid_holdup()

    # ------------------------------------------------------------------
    # Friction factor  (Jain / Colebrook approximation)
    # ------------------------------------------------------------------

    def frictional_factor(self, Hl: float) -> float:
        """
        Calculates the two-phase Darcy friction factor using the Jain (1976)
        explicit approximation to the Colebrook-White equation.

        Uses the standard oilfield Re definition:
            Re = 1488 * rho_ns [lbm/ft³] * Vm [ft/s] * d [ft] / mu_m [cp]

        Args:
            Hl (float): Liquid holdup fraction (dimensionless), passed in from
                    calculate_gradient() to avoid a redundant holdup call.

        Returns:
            float: Darcy-Weisbach friction factor (dimensionless).
        """
        lambda_l = self.fp["Vsl"] / max(self.fp["Vm"], 1e-6)

    # No-slip mixture density — weighted by input-liquid fraction [lbm/ft³]
        self.fp["rho_ns"] = (
        self.fp["rho_l"] * lambda_l
        + self.fp["rho_g"] * (1.0 - lambda_l)
        )

    # Hagedorn-Brown mixture viscosity — weighted exponential [cp]
        mu_m = (
        self.fp["mu_l"] ** Hl
        * self.fp["mu_g"] ** (1.0 - Hl)
        )

    # ── BUG FIX 1 ────────────────────────────────────────────────────────
    # Original code used  2.2e-2 * Ql * fp["M"] / (tid * mu_m)
    # which is dimensionally wrong (lbm²/day² in the numerator, not a
    # velocity × density product). The correct oilfield Reynolds number is:
    #
    #   Re = 1488 * rho [lbm/ft³] * Vm [ft/s] * D [ft] / mu [cp]
    #
    # The constant 1488 converts:  (lbm/ft³)(ft/s)(ft) / cp  →  dimensionless
    # i.e.  1 cp = 6.72e-4 lbm/(ft·s),  and  1/6.72e-4 ≈ 1488.
    # ─────────────────────────────────────────────────────────────────────
        Re = (
        1488.0
        * self.fp["rho_ns"]   # [lbm/ft³]
        * self.fp["Vm"]       # [ft/s]
        * self.tid            # [ft]
        / mu_m                # [cp]
        )

    # Laminar regime — exact Hagen-Poiseuille result
        if Re < 2000:
            return 64.0 / max(Re, 1.0)

    # ── BUG FIX 2 ────────────────────────────────────────────────────────
    # Original code passed  self.roughness  (absolute roughness, ft) directly
    # into the Jain log term.  Jain / Colebrook-White require the
    # RELATIVE roughness  e/D  (dimensionless).  At typical values:
    #
    #   e = 0.0006 ft,  D = 0.2034 ft  →  e/D ≈ 0.00295
    #
    # Passing 0.0006 instead of 0.00295 gives a roughness ~5× too low,
    # producing an underestimated friction factor in the turbulent regime.
    # ─────────────────────────────────────────────────────────────────────
        relative_roughness = self.roughness / self.tid   # dimensionless [ft/ft]

    # Jain (1976) explicit approximation — accurate to ±1 % for
    # Re ∈ [3 000, 4×10⁸] and e/D ∈ [4×10⁻⁵, 0.05].
    # This covers virtually every wellbore multiphase flow condition,
    # so there is no practical need to iterate Colebrook-White here.
        f = (1.14 - 2.0 * np.log10(relative_roughness + 21.25 / (Re ** 0.9))) ** -2

        return f

    # ------------------------------------------------------------------
    # Pressure gradient
    # ------------------------------------------------------------------

    def calculate_gradient(self):
        """
        Calculates the total multiphase pressure gradient (psi/ft).

        Routes holdup through get_holdup() which selects Griffith (bubble)
        or Hagedorn-Brown (slug/mist) automatically.

        Returns:
            float: Total pressure gradient in psi/ft.
        """
        Hl = self.get_holdup()
        f  = self.frictional_factor(Hl)

        dp_dh_el   = self.fp["rho_m"] * np.cos(self.theta) / 144.0
        gc         = 32.174
        dp_dh_fric = (f * self.fp["rho_ns"] * self.fp["Vm"] ** 2) / (2.0 * gc * self.tid * 144.0)

        return dp_dh_el + dp_dh_fric

    # ------------------------------------------------------------------
    # Pressure traverse
    # ------------------------------------------------------------------

    def calculate_pressure_traverse(self, Pth, surface_temp, bottomhole_temp,
                                    total_depth, step_size, Ql):
        """
        Calculates the wellbore pressure profile via Euler integration.

        Returns:
            tuple: (depths [ft], pressures [psia])
        """
        depths        = [0.0]
        pressures     = [Pth]
        current_P     = Pth
        current_depth = 0.0
        temp_gradient = (bottomhole_temp - surface_temp) / total_depth

        while current_depth < total_depth:
            next_depth   = min(current_depth + step_size, total_depth)
            actual_step  = next_depth - current_depth
            current_temp = surface_temp + temp_gradient * current_depth

            self.update_fluid_properties(current_P, current_temp, Ql)
            dp_dz     = self.calculate_gradient()
            current_P += dp_dz * actual_step
            current_depth = next_depth

            depths.append(current_depth)
            pressures.append(current_P)

        return depths, pressures

    # ------------------------------------------------------------------
    # Plotting helpers
    # ------------------------------------------------------------------

    def plot_pressure_traverse(self, Pth, surface_temp, bottomhole_temp,
                               total_depth, step_size, Ql):
        depths, pressures = self.calculate_pressure_traverse(
            Pth, surface_temp, bottomhole_temp, total_depth, step_size, Ql
        )
        plt.plot(pressures, depths, color='blue', linewidth=2)
        plt.gca().invert_yaxis()
        plt.xlabel('Pressure (psia)')
        plt.ylabel('Depth (ft)')
        plt.title('Pressure Traverse Curve')
        plt.grid(True)
        plt.show()
        return pressures[-1]

    def plot_vlp_curve(self, Pth, surface_temp, bottomhole_temp,
                       depth, Qmin, Qmax, step_size):
        Pwf_points = []
        rates = np.linspace(Qmin, Qmax, Qmax - Qmin)

        for q in rates:
            _, pressures = self.calculate_pressure_traverse(
                Pth, surface_temp, bottomhole_temp, depth, step_size, q
            )
            Pwf_points.append(pressures[-1])

        plt.plot(rates, Pwf_points, color='blue')
        plt.xlabel('Liquid Rate (stb/day)')
        plt.ylabel('Pwf (psi)')
        plt.title('VLP Curve')
        plt.grid(True)
        plt.show()

    def vlp_curve_plot_linear(self, Pth, depth, Qmin, Qmax, step_size):
        """Simplified single-gradient VLP (stale PVT — approximate only)."""
        Pwf_points = []
        rates = np.linspace(Qmin, Qmax, int((Qmax - Qmin) / step_size))

        for q in rates:
            self.Ql = q
            Pwf = Pth + self.calculate_gradient() * depth
            Pwf_points.append(Pwf)

        plt.plot(rates, Pwf_points, color='blue')
        plt.xlabel('Liquid Rate (stb/day)')
        plt.ylabel('Pwf (psi)')