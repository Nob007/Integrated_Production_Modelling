import numpy as np
import pandas as pd
from scipy.optimize import minimize
import copy


def apply_calibration_factors(model, holdup_factor: float, friction_factor: float):
    """
    Creates a deep copy of a VLP model and wraps its gradient calculation
    methods to apply calibration factors. This is a standalone utility function.

    Args:
        model: An instantiated VLP model object (e.g., HagedornBrown).
        holdup_factor (float): The multiplier for the liquid holdup.
        friction_factor (float): The multiplier for the friction factor.

    Returns:
        A new, calibrated VLP model instance.
    """
    calibrated_model = copy.deepcopy(model)

    # Store original methods
    original_get_holdup = calibrated_model.get_holdup
    original_frictional_factor = calibrated_model.frictional_factor

    # Create new wrapped methods that apply the factors
    def calibrated_get_holdup(*args, **kwargs):
        # The original get_holdup for HagedornBrown returns a tuple of values.
        # We need to apply the factor only to the first element (Hl).
        original_output = original_get_holdup(*args, **kwargs)
        if isinstance(original_output, tuple):
            original_hl, *rest = original_output
            calibrated_hl = min(original_hl * holdup_factor, 1.0)
            return (calibrated_hl, *rest)
        return min(original_output * holdup_factor, 1.0)

    def calibrated_frictional_factor(*args, **kwargs):
        return original_frictional_factor(*args, **kwargs) * friction_factor

    # Monkey-patch the instance with the new calibrated methods
    calibrated_model.get_holdup = calibrated_get_holdup
    calibrated_model.frictional_factor = calibrated_frictional_factor

    return calibrated_model


class VLPCalibrator:
    """
    Calibrates a VLP model (Hagedorn-Brown or Beggs-Brill) against measured
    pressure data by adjusting holdup and friction factors.
    """

    def __init__(self, vlp_model, traverse_params: dict):
        """
        Initializes the calibrator with a base VLP model.

        Args:
            vlp_model: An instantiated VLP model object (e.g., HagedornBrown).
            traverse_params (dict): The parameters required to run a pressure
                traverse (Pth, temperatures, depth, Ql, etc.).
        """
        self.base_model = vlp_model
        self.params = traverse_params
        self.calibrated_model = None
        self.result = None

    def _objective_function(self, factors, measured_depths, measured_pressures):
        """
        The function to minimize: the sum of squared errors between calculated
        and measured pressures.

        Args:
            factors (list): A list containing [holdup_factor, friction_factor].
            measured_depths (list): Depths from the well test.
            measured_pressures (list): Pressures from the well test.

        Returns:
            float: The sum of squared errors (SSE).
        """
        holdup_factor, friction_factor = factors

        # Create a temporary, modified VLP model for this iteration
        temp_model = apply_calibration_factors(self.base_model, holdup_factor, friction_factor)

        # Calculate the pressure traverse with the modified model
        try:
            calc_depths, calc_pressures, _ = temp_model.calculate_pressure_traverse(
                **self.params
            )
        except Exception:
            # Return a large error if the solver fails
            return 1e12

        # Interpolate calculated pressures at the same depths as measured data
        # to ensure a fair comparison.
        interp_pressures = np.interp(measured_depths, calc_depths, calc_pressures)

        # Calculate the sum of squared errors
        error = np.sum((interp_pressures - measured_pressures) ** 2)
        return error

    def run(self, measured_depths, measured_pressures, initial_guess=[1.0, 1.0]):
        """
        Runs the optimization process to find the best calibration factors.

        Args:
            measured_depths (list or np.array): Measured depths from a survey.
            measured_pressures (list or np.array): Measured pressures corresponding
                to the depths.
            initial_guess (list, optional): Starting values for [holdup_factor,
                friction_factor]. Defaults to [1.0, 1.0].

        Returns:
            scipy.optimize.OptimizeResult: The result object from the optimizer.
        """
        # Ensure data is numpy array
        md = np.array(measured_depths)
        mp = np.array(measured_pressures)

        # Run the minimization
        self.result = minimize(
            self._objective_function,
            x0=initial_guess,
            args=(md, mp),
            method='Nelder-Mead',  # A robust method for this type of problem
            options={'xatol': 1e-3, 'fatol': 1e-3, 'disp': True}
        )

        if self.result.success:
            # If successful, create the final calibrated model
            best_factors = self.result.x
            self.calibrated_model = apply_calibration_factors(self.base_model, best_factors[0], best_factors[1])
            print(f"Calibration successful! Optimal Factors: Holdup={best_factors[0]:.4f}, Friction={best_factors[1]:.4f}")

        return self.result