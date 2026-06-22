import numpy as np
from scipy.optimize import root_scalar

def find_operating_point(ipr_model, vlp_model, vlp_params, q_min=100.0, q_max=None):
    """
    Finds the intersection point (operating point) of the IPR and VLP curves.

    Args:
        ipr_model (composite_ipr): An initialized instance of the composite_ipr class.
        vlp_model (HagedornBrown): An initialized instance of the HagedornBrown class.
        vlp_params (dict): Dictionary containing structural and profile parameters needed
                           by the vlp_model.calculate_pressure_traverse method.
                           Expected keys: 'Pth', 'surface_temp', 'bottomhole_temp', 
                                          'depth', 'step_size'
        q_min (float): Lower bound for the flow rate search range (STB/day).
        q_max (float, optional): Upper bound for the flow rate search range. Defaults to ipr_model.q_max.

    Returns:
        dict: A dictionary containing 'operating_rate', 'operating_pwf', 'success', and 'message'.
    """
    # 1. Fallback to the absolute open flow limit of the reservoir if no upper limit is passed
    if q_max is None:
        q_max = ipr_model.q_max

    # 2. Define the objective function we want to minimize or find the root for
    def objective_function(q):
        # Calculate Pwf from the Reservoir side (IPR)
        p_wf_ipr = ipr_model.calculate_Pwf(q)
        
        # Calculate Pwf from the Wellbore side (VLP)
        # Note: calculate_pressure_traverse returns a tuple (depths, pressures, profiles). 
        # The bottom-hole pressure is the last element [-1] in the pressures list.
        _, pressures, _ = vlp_model.calculate_pressure_traverse(
            Pth=vlp_params['Pth'],
            surface_temp=vlp_params['surface_temp'],
            bottomhole_temp=vlp_params['bottomhole_temp'],
            depth=vlp_params['depth'],
            step_size=vlp_params['step_size'],
            Ql=q
        )
        p_wf_vlp = pressures[-1]
        
        # We want: Pwf_vlp - Pwf_ipr = 0
        return p_wf_vlp - p_wf_ipr

    # 3. Check for boundaries to see if a valid intersection exists within the range
    try:
        f_min = objective_function(q_min)
        f_max = objective_function(q_max)
    except Exception as e:
        return {
            "success": False,
            "operating_rate": None,
            "operating_pwf": None,
            "message": f"Error during boundary evaluation: {str(e)}"
        }

    # In nodal analysis, if f_min and f_max have the same sign, the curves don't cross 
    # (e.g., the well cannot flow due to high tubing friction/hydrostatic pressure, or it always flows above q_max)
    if np.sign(f_min) == np.sign(f_max):
        # Determine the physical reason for failing to cross
        if f_min > 0:
            msg = "The well cannot flow. VLP pressure requirements exceed IPR capability even at minimum flow."
        else:
            msg = f"Operating point exceeds the Reservoir Absolute Open Flow limit ({q_max:.1f} STB/D)."
        return {
            "success": False,
            "operating_rate": None,
            "operating_pwf": None,
            "message": msg
        }

    # 4. Perform root finding using Brent's method (highly reliable and safe root-finding tool)
    try:
        sol = root_scalar(objective_function, bracket=[q_min, q_max], method='brentq', xtol=1e-2)
        
        if sol.converged:
            operating_q = sol.root
            operating_p = ipr_model.calculate_Pwf(operating_q)
            return {
                "success": True,
                "operating_rate": operating_q,
                "operating_pwf": operating_p,
                "message": "Success! Operating point resolved."
            }
        else:
            return {
                "success": False,
                "operating_rate": None,
                "operating_pwf": None,
                "message": "Solver executed but failed to converge."
            }
            
    except Exception as e:
        return {
            "success": False,
            "operating_rate": None,
            "operating_pwf": None,
            "message": f"Solver optimization error: {str(e)}"
        }