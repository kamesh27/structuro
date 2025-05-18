# section_calculator.py
# Main application file for the Sectional Properties Calculator

import math
import json
from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO  
import openpyxl
import scipy.integrate as spi

# --- Constants ---
PI = math.pi

PROPERTY_NAME_MAP = {
    "A": "Cross-Sectional Area",
    "Xc": "Centroid X-coordinate",
    "Yc": "Centroid Y-coordinate",
    "Ixx": "Moment of Inertia about x-axis",
    "Iyy": "Moment of Inertia about y-axis",
    "Ixy": "Product of Inertia about x-y axes",
    "theta_p": "Angle to Principal Axes",
    "I1": "Major Principal Moment of Inertia (Iu)",
    "I2": "Minor Principal Moment of Inertia (Iv)",
    "rx": "Radius of Gyration about x-axis",
    "ry": "Radius of Gyration about y-axis",
    "r1": "Radius of Gyration about major principal axis (ru)",
    "r2": "Radius of Gyration about minor principal axis (rv)",
    "Sx_top": "Elastic Section Modulus about x-axis (to top fiber)",
    "Sx_bottom": "Elastic Section Modulus about x-axis (to bottom fiber)",
    "Sy_left": "Elastic Section Modulus about y-axis (to left fiber)",
    "Sy_right": "Elastic Section Modulus about y-axis (to right fiber)",
    "S1": "Elastic Section Modulus about major principal axis (Su)",
    "S2": "Elastic Section Modulus about minor principal axis (Sv)",
    "Zx": "Plastic Section Modulus about x-axis",
    "Zy": "Plastic Section Modulus about y-axis",
    "J": "Torsional Constant",
    "Cw": "Warping Constant",
    "n_modular_ratio": "Modular Ratio (n)",
    "A_tr": "Transformed Area",
    "YNA_tr": "Neutral Axis of Transformed Section (from datum)",
    "I_tr": "Moment of Inertia of Transformed Section",
    "Str_top_concrete": "Elastic Modulus (Transformed) - Top Concrete",
    "Str_bottom_steel": "Elastic Modulus (Transformed) - Bottom Steel",
    "Str_top_steel": "Elastic Modulus (Transformed) - Top Steel",
    "yct_top_concrete": "Distance NA to Top Concrete",
    "ysb_bottom_steel": "Distance NA to Bottom Steel",
    "yst_top_steel": "Distance NA to Top Steel",
    "y_top": "Distance Centroid to Top Fiber",
    "y_bottom": "Distance Centroid to Bottom Fiber",
    "x_left": "Distance Centroid to Left Fiber",
    "x_right": "Distance Centroid to Right Fiber",
    # Dimension keys for input sheet in Excel
    "d": "Overall Depth",
    "bf": "Flange Width",
    "tf": "Flange Thickness",
    "tw": "Web Thickness",
    "h": "Height",
    "b": "Width",
    "OD": "Outer Diameter",
    "ID": "Inner Diameter", # Though thickness is usually input
    "t": "Thickness",
    "L1": "Leg 1 Length",
    "L2": "Leg 2 Length",
    "H": "Overall Depth (HSS)",
    "B": "Overall Width (HSS)",
    "ts": "Stem Thickness (Tee)",
    "D": "Diameter (Solid Circle)"
}

# --- Unit System Management ---
class UnitSystem:
    def __init__(self, base_units=None):
        if base_units is None:
            self.base_units = {
                "length": "mm", "area": "mm^2", "moment_of_inertia": "mm^4",
                "section_modulus": "mm^3", "radius_of_gyration": "mm",
                "force": "N", "moment": "N-mm", "stress": "MPa",
                "torsional_constant": "mm^4", "warping_constant": "mm^6"
            }
        else:
            self.base_units = base_units
        self.current_system_name = "METRIC_MM_N"
        self.conversion_factors = self._get_conversion_factors()
        if self.current_system_name in self.conversion_factors:
             self.display_units = self.conversion_factors[self.current_system_name]["display_units"]
        else:
            self.display_units = {}

    def _get_conversion_factors(self):
        return {
            "METRIC_MM_N": {"length": 1.0, "force": 1.0, "stress": 1.0, "display_units": {"length": "mm", "area": "mm²", "moment_of_inertia": "mm⁴", "section_modulus": "mm³", "radius_of_gyration": "mm", "force": "N", "moment": "N·mm", "stress": "MPa", "torsional_constant": "mm⁴", "warping_constant": "mm⁶", "angle": "deg"}},
            "METRIC_M_KN": {"length": 1000.0, "force": 1000.0, "stress": 1.0, "display_units": {"length": "m", "area": "m²", "moment_of_inertia": "m⁴", "section_modulus": "m³", "radius_of_gyration": "m", "force": "kN", "moment": "kN·m", "stress": "MPa", "torsional_constant": "m⁴", "warping_constant": "m⁶", "angle": "deg"}},
            "IMPERIAL_IN_KIPS": {"length": 25.4, "force": 4448.22, "stress": 4448.22 / (25.4**2), "display_units": {"length": "in", "area": "in²", "moment_of_inertia": "in⁴", "section_modulus": "in³", "radius_of_gyration": "in", "force": "kips", "moment": "kip·in", "stress": "ksi", "torsional_constant": "in⁴", "warping_constant": "in⁶", "angle": "deg"}},
        }

    def set_system(self, system_name):
        if system_name in self.conversion_factors:
            self.current_system_name = system_name
            self.display_units = self.conversion_factors[self.current_system_name]["display_units"]
        else:
            raise ValueError(f"Unknown unit system: {system_name}")

    def to_base_units(self, value, unit_type):
        factors = self.conversion_factors[self.current_system_name]
        if unit_type == "length": return value * factors["length"]
        elif unit_type == "force": return value * factors["force"]
        elif unit_type == "stress": return value * factors["stress"]
        elif unit_type == "area": return value * (factors["length"]**2)
        elif unit_type == "moment_of_inertia": return value * (factors["length"]**4)
        elif unit_type == "section_modulus": return value * (factors["length"]**3)
        elif unit_type == "radius_of_gyration": return value * factors["length"]
        elif unit_type == "torsional_constant": return value * (factors["length"]**4)
        elif unit_type == "warping_constant": return value * (factors["length"]**6)
        else: raise ValueError(f"Unknown unit type for conversion: {unit_type}")

    def from_base_units(self, value_base, unit_type):
        factors = self.conversion_factors[self.current_system_name]
        if unit_type == "length": return value_base / factors["length"]
        elif unit_type == "force": return value_base / factors["force"]
        elif unit_type == "stress": return value_base / factors["stress"]
        elif unit_type == "area": return value_base / (factors["length"]**2)
        elif unit_type == "moment_of_inertia": return value_base / (factors["length"]**4)
        elif unit_type == "section_modulus": return value_base / (factors["length"]**3)
        elif unit_type == "radius_of_gyration": return value_base / factors["length"]
        elif unit_type == "torsional_constant": return value_base / (factors["length"]**4)
        elif unit_type == "warping_constant": return value_base / (factors["length"]**6)
        else: raise ValueError(f"Unknown unit type for conversion: {unit_type}")

    def get_display_unit_symbol(self, unit_type_str):
        return self.display_units.get(unit_type_str, "")

# --- Base Section Class ---
class Section:
    def __init__(self, unit_system_obj):
        self.unit_system = unit_system_obj
        self.properties = {} 
        self.input_dims = {} 

    def _convert_inputs_to_base(self, dims_map):
        base_dims = {}
        for key, (value, unit_type) in dims_map.items():
            base_dims[key] = self.unit_system.to_base_units(value, unit_type)
        return base_dims

    def calculate_properties(self):
        raise NotImplementedError("Subclasses must implement calculate_properties.")

    def get_properties_in_display_units(self):
        results_to_send = {}
        for key, unconverted_value_base in self.properties.items():
            unit_type_for_conversion = "unitless" 
            converted_value = unconverted_value_base 

            if key in ["A", "A_tr"]: unit_type_for_conversion = "area"
            elif key in ["Ixx", "Iyy", "Ixy", "I1", "I2", "J", "I_tr", "Ix_prime", "Iy_prime"]: unit_type_for_conversion = "moment_of_inertia"
            elif key == "Cw": unit_type_for_conversion = "warping_constant"
            elif key in ["Sx_top", "Sx_bottom", "Sy_left", "Sy_right", "S1", "S2", "Zx", "Zy",
                         "Str_top_concrete", "Str_bottom_steel", "Str_top_steel"]: unit_type_for_conversion = "section_modulus"
            elif key in ["rx", "ry", "r1", "r2", "Xc", "Yc", "YNA_tr",
                         "ytop", "ybottom", "xleft", "xright",
                         "yct_top_concrete", "ysb_bottom_steel", "yst_top_steel"]: unit_type_for_conversion = "length"
            elif key == "theta_p": unit_type_for_conversion = "angle"
            
            if unconverted_value_base is None:
                converted_value = None
            elif unit_type_for_conversion == "angle":
                converted_value = math.degrees(unconverted_value_base)
            elif unit_type_for_conversion != "unitless" and self.unit_system.display_units.get(unit_type_for_conversion):
                converted_value = self.unit_system.from_base_units(unconverted_value_base, unit_type_for_conversion)

            results_to_send[key] = {
                "name": PROPERTY_NAME_MAP.get(key, key), 
                "symbol": key, 
                "value": converted_value,
                "unit": self.unit_system.get_display_unit_symbol(unit_type_for_conversion)
            }
        return results_to_send

    def _calculate_general_properties(self):
        A = self.properties.get("A")
        Ixx_c = self.properties.get("Ixx")
        Iyy_c = self.properties.get("Iyy")
        Ixy_c = self.properties.get("Ixy", 0)

        if A is None or Ixx_c is None or Iyy_c is None: return

        if A > 1e-9: 
            self.properties["rx"] = math.sqrt(Ixx_c / A) if Ixx_c / A >= 0 else 0
            self.properties["ry"] = math.sqrt(Iyy_c / A) if Iyy_c / A >= 0 else 0

        y_top = self.properties.get("y_top")
        y_bottom = self.properties.get("y_bottom")
        x_left = self.properties.get("x_left")
        x_right = self.properties.get("x_right")

        if y_top is not None and abs(y_top) > 1e-9: self.properties["Sx_top"] = Ixx_c / y_top
        if y_bottom is not None and abs(y_bottom) > 1e-9: self.properties["Sx_bottom"] = Ixx_c / y_bottom
        if x_left is not None and abs(x_left) > 1e-9: self.properties["Sy_left"] = Iyy_c / x_left
        if x_right is not None and abs(x_right) > 1e-9: self.properties["Sy_right"] = Iyy_c / x_right
        
        if abs(Ixy_c) > 1e-9 * max(abs(Ixx_c), abs(Iyy_c), 1.0): 
            avg_I = (Ixx_c + Iyy_c) / 2
            diff_I_half = (Ixx_c - Iyy_c) / 2
            sqrt_arg = diff_I_half**2 + Ixy_c**2
            R_val = math.sqrt(sqrt_arg) if sqrt_arg >= 0 else 0
            self.properties["I1"], self.properties["I2"] = avg_I + R_val, avg_I - R_val
            if abs(diff_I_half) < 1e-9 and abs(Ixy_c) < 1e-9 : self.properties["theta_p"] = 0.0 
            elif abs(diff_I_half) < 1e-9 : self.properties["theta_p"] = math.radians(-45 if Ixy_c > 0 else 45) 
            else: self.properties["theta_p"] = 0.5 * math.atan2(-2 * Ixy_c, Ixx_c - Iyy_c) 
            if A > 1e-9:
                if self.properties.get("I1", 0) / A >= 0: self.properties["r1"] = math.sqrt(self.properties["I1"] / A)
                if self.properties.get("I2", 0) / A >= 0: self.properties["r2"] = math.sqrt(self.properties["I2"] / A)
        else: 
            self.properties["I1"], self.properties["I2"] = Ixx_c, Iyy_c
            self.properties["theta_p"] = 0.0 
            if A > 1e-9:
                self.properties["r1"], self.properties["r2"] = self.properties.get("rx"), self.properties.get("ry")

# --- Standard Rolled Section ---
class StandardRolledSection(Section):
    def __init__(self, unit_system_obj, shape_type, standard_code=None, section_data=None, manual_dims=None):
        super().__init__(unit_system_obj)
        self.shape_type = shape_type
        self.standard_code = standard_code
        self.section_data_from_lib = section_data
        self.manual_dims_input = manual_dims

        if self.section_data_from_lib:
            self._load_from_library()
        elif self.manual_dims_input:
            self._process_manual_dims()
        else:
            raise ValueError("Either section_data (library) or manual_dims must be provided.")

    def _load_from_library(self):
        # Store base dimensions first, as they are needed for calculations
        self.input_dims_converted_to_base = {}
        # Always load these core dimensions if available
        core_dims_to_load = ["d_base", "bf_base", "tf_base", "tw_base", "h_base", "b_base", "OD_base", "ID_base", "t_base", "L1_base", "L2_base", "H_base", "B_base", "ts_base", "D_base"]
        for dim_key_with_suffix in core_dims_to_load:
            if dim_key_with_suffix in self.section_data_from_lib:
                dim_key = dim_key_with_suffix.replace("_base", "")
                self.input_dims_converted_to_base[dim_key] = self.section_data_from_lib[dim_key_with_suffix]

        # Load Area (A)
        self.properties["A"] = self.section_data_from_lib.get("A_base")
        self.properties["Xc"] = 0 # Assume centroid at origin for library sections initially
        self.properties["Yc"] = 0

        if self.standard_code == "INDIAN_SP6":
            # For INDIAN_SP6, only A, d, bf, tf, tw are used from library.
            # Other properties will be calculated.
            # Ensure the necessary dimensions are in input_dims_converted_to_base
            # (already handled by loading core_dims_to_load)
            pass # No further properties loaded from library for SP6
        else:
            # For other standards, load all available pre-calculated properties
            self.properties["Ixx"] = self.section_data_from_lib.get("Ixx_base")
            self.properties["Iyy"] = self.section_data_from_lib.get("Iyy_base")
            self.properties["Ixy"] = self.section_data_from_lib.get("Ixy_base", 0)
            self.properties["J"] = self.section_data_from_lib.get("J_base")
            self.properties["Cw"] = self.section_data_from_lib.get("Cw_base")
            self.properties["Zx"] = self.section_data_from_lib.get("Zx_base")
            self.properties["Zy"] = self.section_data_from_lib.get("Zy_base")

        # Calculate y_top, y_bottom, etc. based on loaded dimensions
        d_base = self.input_dims_converted_to_base.get("d")
        bf_base = self.input_dims_converted_to_base.get("bf")
        od_base = self.input_dims_converted_to_base.get("OD", self.input_dims_converted_to_base.get("D"))
        h_rect_base = self.input_dims_converted_to_base.get("H", self.input_dims_converted_to_base.get("h"))
        b_rect_base = self.input_dims_converted_to_base.get("B", self.input_dims_converted_to_base.get("b"))

        if d_base is not None:
            self.properties["y_top"], self.properties["y_bottom"] = d_base / 2, d_base / 2
        elif od_base is not None:
             self.properties["y_top"], self.properties["y_bottom"] = od_base / 2, od_base / 2
        elif h_rect_base is not None:
            self.properties["y_top"], self.properties["y_bottom"] = h_rect_base / 2, h_rect_base / 2

        if bf_base is not None:
            self.properties["x_left"], self.properties["x_right"] = bf_base / 2, bf_base / 2
        elif od_base is not None:
            self.properties["x_left"], self.properties["x_right"] = od_base / 2, od_base / 2
        elif b_rect_base is not None:
            self.properties["x_left"], self.properties["x_right"] = b_rect_base / 2, b_rect_base / 2

        self.input_dims = self.section_data_from_lib.get("dimensions_display", {}) # Keep display dims for info

    def _process_manual_dims(self):
        self.input_dims_converted_to_base = self._convert_inputs_to_base(self.manual_dims_input)
        if self.shape_type == "SolidRectangle": self._calculate_solid_rectangle_integration()
        elif self.shape_type == "I-Beam": self._calculate_i_beam_integration()
        elif self.shape_type == "SolidCircle": self._calculate_solid_circle_integration()
        elif self.shape_type == "Channel": self._calculate_channel_integration()
        elif self.shape_type == "Angle": self._calculate_angle_integration()
        elif self.shape_type == "Tee": self._calculate_tee_integration()
        elif self.shape_type == "HSS-Rectangular": self._calculate_hss_rectangular_integration()
        elif self.shape_type == "HSS-Circular": self._calculate_hss_circular_integration()
        else: raise NotImplementedError(f"Manual calculation for {self.shape_type} not yet implemented.")

    def _integrate_rectangle_part(self, width, height, x_offset_corner, y_offset_corner):
        """
        Integrates properties for a rectangular part.
        x_offset_corner, y_offset_corner are coordinates of the bottom-left corner of the rectangle
        relative to the common origin for the entire section.
        """
        x_min_part = x_offset_corner
        x_max_part = x_offset_corner + width
        y_min_part = y_offset_corner
        y_max_part = y_offset_corner + height

        area_integrand = lambda y, x: 1
        Qx_integrand = lambda y, x: y
        Qy_integrand = lambda y, x: x
        Ixx_o_integrand = lambda y, x: y**2
        Iyy_o_integrand = lambda y, x: x**2
        Ixy_o_integrand = lambda y, x: x * y

        A_part, _ = spi.dblquad(area_integrand, x_min_part, x_max_part, lambda x: y_min_part, lambda x: y_max_part)
        Qx_part, _ = spi.dblquad(Qx_integrand, x_min_part, x_max_part, lambda x: y_min_part, lambda x: y_max_part)
        Qy_part, _ = spi.dblquad(Qy_integrand, x_min_part, x_max_part, lambda x: y_min_part, lambda x: y_max_part)
        Ixx_o_part, _ = spi.dblquad(Ixx_o_integrand, x_min_part, x_max_part, lambda x: y_min_part, lambda x: y_max_part)
        Iyy_o_part, _ = spi.dblquad(Iyy_o_integrand, x_min_part, x_max_part, lambda x: y_min_part, lambda x: y_max_part)
        Ixy_o_part, _ = spi.dblquad(Ixy_o_integrand, x_min_part, x_max_part, lambda x: y_min_part, lambda x: y_max_part)
        
        return A_part, Qx_part, Qy_part, Ixx_o_part, Iyy_o_part, Ixy_o_part

    def _integrate_solid_circular_part(self, R_dim):
        """Integrates properties for a solid circular part of radius R_dim centered at origin."""
        if R_dim < 1e-9: # Effectively no circle
            return 0, 0, 0, 0, 0, 0, 0

        area_integrand = lambda y, x: 1
        Qx_integrand = lambda y, x: y
        Qy_integrand = lambda y, x: x
        Ixx_o_integrand = lambda y, x: y**2
        Iyy_o_integrand = lambda y, x: x**2
        Ixy_o_integrand = lambda y, x: x * y
        J_integrand = lambda y, x: x**2 + y**2

        y_limit_func = lambda x: math.sqrt(R_dim**2 - x**2) if R_dim**2 - x**2 >= 0 else 0
        
        A, _ = spi.dblquad(area_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        Qx, _ = spi.dblquad(Qx_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        Qy, _ = spi.dblquad(Qy_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        Ixx_o, _ = spi.dblquad(Ixx_o_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        Iyy_o, _ = spi.dblquad(Iyy_o_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        Ixy_o, _ = spi.dblquad(Ixy_o_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        J_val, _ = spi.dblquad(J_integrand, -R_dim, R_dim, lambda x: -y_limit_func(x), lambda x: y_limit_func(x))
        return A, Qx, Qy, Ixx_o, Iyy_o, Ixy_o, J_val

    def _calculate_solid_rectangle_integration(self):
        b_dim = self.input_dims_converted_to_base.get("b")
        h_dim = self.input_dims_converted_to_base.get("h")
        if b_dim is None or h_dim is None: raise ValueError("Width (b) and Height (h) must be provided.")
        if b_dim <=0 or h_dim <=0: raise ValueError("Dimensions must be positive.")

        # Origin at the geometric center of the rectangle
        A, Qx_o, Qy_o, Ixx_o, Iyy_o, Ixy_o = \
            self._integrate_rectangle_part(b_dim, h_dim, -b_dim/2, -h_dim/2)
        
        Xc = Qy_o / A if A != 0 else 0
        Yc = Qx_o / A if A != 0 else 0
        
        Ixx = Ixx_o - A * Yc**2 # Yc should be 0
        Iyy = Iyy_o - A * Xc**2 # Xc should be 0
        Ixy = Ixy_o - A * Xc * Yc # Xc, Yc should be 0

        J_val = 0
        if max(b_dim, h_dim) > 1e-9:
            ratio = min(b_dim, h_dim) / max(b_dim, h_dim)
            J_val = (1/3) * (1 - 0.63 * ratio + 0.052 * ratio**5) * max(b_dim, h_dim) * min(b_dim, h_dim)**3
        
        self.properties.update({
            "A": A, "Xc": Xc, "Yc": Yc, 
            "Ixx": Ixx, "Iyy": Iyy, "Ixy": Ixy,
            "y_top": h_dim/2 - Yc, "y_bottom": h_dim/2 + Yc, 
            "x_left": b_dim/2 + Xc, "x_right": b_dim/2 - Xc,
            "J": J_val, "Cw": 0, 
            "Zx": (b_dim * h_dim**2)/4, 
            "Zy": (h_dim * b_dim**2)/4
        })

    def _calculate_i_beam_integration(self):
        d = self.input_dims_converted_to_base.get("d")      
        bf = self.input_dims_converted_to_base.get("bf")    
        tf = self.input_dims_converted_to_base.get("tf")    
        tw = self.input_dims_converted_to_base.get("tw")    
        
        if None in [d, bf, tf, tw]: raise ValueError("d, bf, tf, tw must be provided for I-Beam.")
        if d <=0 or bf <=0 or tf <=0 or tw <=0: raise ValueError("I-Beam dimensions must be positive.")
        hw = d - 2 * tf 
        if hw <= 0 : raise ValueError("Web height (d - 2*tf) must be positive for I-Beam.")

        A_web, Qx_web_o, Qy_web_o, Ixx_o_web, Iyy_o_web, Ixy_o_web = \
            self._integrate_rectangle_part(tw, hw, -tw/2, -hw/2)
        A_tf, Qx_tf_o, Qy_tf_o, Ixx_o_tf, Iyy_o_tf, Ixy_o_tf = \
            self._integrate_rectangle_part(bf, tf, -bf/2, hw/2)
        A_bf, Qx_bf_o, Qy_bf_o, Ixx_o_bf, Iyy_o_bf, Ixy_o_bf = \
            self._integrate_rectangle_part(bf, tf, -bf/2, -d/2)

        A_total = A_web + A_tf + A_bf
        Qx_total_o = Qx_web_o + Qx_tf_o + Qx_bf_o
        Qy_total_o = Qy_web_o + Qy_tf_o + Qy_bf_o
        Ixx_total_o = Ixx_o_web + Ixx_o_tf + Ixx_o_bf
        Iyy_total_o = Iyy_o_web + Iyy_o_tf + Iyy_o_bf
        Ixy_total_o = Ixy_o_web + Ixy_o_tf + Ixy_o_bf
        
        Xc_total = Qy_total_o / A_total if A_total > 1e-9 else 0 # Should be 0
        Yc_total = Qx_total_o / A_total if A_total > 1e-9 else 0 # Should be 0
        
        Ixx_total_c = Ixx_total_o - A_total * Yc_total**2
        Iyy_total_c = Iyy_total_o - A_total * Xc_total**2
        Ixy_total_c = Ixy_total_o - A_total * Xc_total * Yc_total

        J_val = (1/3) * (2 * bf * tf**3 + hw * tw**3) # Standard St. Venant approximation for open sections
        
        # More accurate Cw formula for doubly symmetric I-sections:
        # Cw = (I_y_flange * h_0^2) / 2
        # where I_y_flange = (tf * bf^3) / 12 (for one flange)
        # and h_0 = d - tf (distance between flange centroids)
        I_y_flange = (tf * bf**3) / 12
        h_0 = d - tf
        Cw_val = (I_y_flange * h_0**2) / 2
        
        Zx_val = (bf * tf * (d - tf)) + (tw * hw**2 / 4)
        Zy_val = (tf * bf**2 / 2) + (hw * tw**2 / 4)

        self.properties.update({
            "A": A_total, "Xc": Xc_total, "Yc": Yc_total,
            "Ixx": Ixx_total_c, "Iyy": Iyy_total_c, "Ixy": Ixy_total_c,
            "y_top": d/2 - Yc_total, "y_bottom": d/2 + Yc_total,
            "x_left": bf/2 + Xc_total, "x_right": bf/2 - Xc_total,
            "J": J_val, "Cw": Cw_val, "Zx": Zx_val, "Zy": Zy_val
        })

    def _calculate_solid_circle_integration(self):
        D_dim = self.input_dims_converted_to_base.get("D")
        if D_dim is None or D_dim <= 0: raise ValueError("Diameter (D) must be positive.")
        R_dim = D_dim / 2

        A, Qx_o, Qy_o, Ixx_o, Iyy_o, Ixy_o, J_val = \
            self._integrate_solid_circular_part(R_dim)
        
        Xc = Qy_o / A if A > 1e-9 else 0 # Should be 0
        Yc = Qx_o / A if A > 1e-9 else 0 # Should be 0

        Ixx = Ixx_o - A * Yc**2
        Iyy = Iyy_o - A * Xc**2
        Ixy = Ixy_o - A * Xc * Yc # Should be 0

        Zx = D_dim**3 / 6
        Zy = Zx

        self.properties.update({
            "A": A, "Xc": Xc, "Yc": Yc, 
            "Ixx": Ixx, "Iyy": Iyy, "Ixy": Ixy,
            "y_top": R_dim - Yc, "y_bottom": R_dim + Yc, 
            "x_left": R_dim + Xc, "x_right": R_dim - Xc,
            "J": J_val, "Cw": 0, "Zx": Zx, "Zy": Zy
        })

    def _calculate_channel_integration(self):
        d_dim = self.input_dims_converted_to_base.get("d")      
        bf_dim = self.input_dims_converted_to_base.get("bf")    
        tf_dim = self.input_dims_converted_to_base.get("tf")    
        tw_dim = self.input_dims_converted_to_base.get("tw")    

        if None in [d_dim, bf_dim, tf_dim, tw_dim] or d_dim <= 0 or bf_dim <= 0 or tf_dim <= 0 or tw_dim <= 0:
            raise ValueError("d, bf, tf, tw must be positive for Channel section.")
        if bf_dim <= tw_dim: raise ValueError("Flange width (bf) must be greater than web thickness (tw) for Channel.")
        if d_dim <= 2*tf_dim: raise ValueError("Overall depth (d) must be greater than twice flange thickness (2*tf) for Channel.")

        hw_dim = d_dim - 2*tf_dim 

        # Origin: Back of the web (x=0), at mid-height of the overall section d (y=0).
        A_w, Qx_w_o, Qy_w_o, Ixx_o_w, Iyy_o_w, Ixy_o_w = \
            self._integrate_rectangle_part(tw_dim, d_dim, 0, -d_dim/2) # Web is full depth d_dim
        
        # Flanges are only on one side of the web for a channel.
        # Top Flange part: width bf_dim, thickness tf_dim.
        # Bottom-left corner relative to origin: (0, d_dim/2 - tf_dim)
        A_tf, Qx_tf_o, Qy_tf_o, Ixx_o_tf, Iyy_o_tf, Ixy_o_tf = \
            self._integrate_rectangle_part(bf_dim, tf_dim, 0, d_dim/2 - tf_dim)

        # Bottom Flange part:
        # Bottom-left corner relative to origin: (0, -d_dim/2)
        A_bf, Qx_bf_o, Qy_bf_o, Ixx_o_bf, Iyy_o_bf, Ixy_o_bf = \
            self._integrate_rectangle_part(bf_dim, tf_dim, 0, -d_dim/2)
            
        A_total = A_w + A_tf + A_bf # This is incorrect for channel, overcounts web-flange intersection
        # Correct decomposition for channel (origin at back of web, mid-depth)
        # Web: tw x d. Origin for this part (0, -d/2)
        A_w, Qx_w_o, Qy_w_o, Ixx_o_w, Iyy_o_w, Ixy_o_w = \
            self._integrate_rectangle_part(tw_dim, d_dim, 0, -d_dim/2)
        # Top Flange (projecting part): (bf_dim - tw_dim) x tf_dim. Origin (tw_dim, d_dim/2 - tf_dim)
        A_tf, Qx_tf_o, Qy_tf_o, Ixx_o_tf, Iyy_o_tf, Ixy_o_tf = \
            self._integrate_rectangle_part(bf_dim - tw_dim, tf_dim, tw_dim, d_dim/2 - tf_dim)
        # Bottom Flange (projecting part): (bf_dim - tw_dim) x tf_dim. Origin (tw_dim, -d_dim/2)
        A_bf, Qx_bf_o, Qy_bf_o, Ixx_o_bf, Iyy_o_bf, Ixy_o_bf = \
            self._integrate_rectangle_part(bf_dim - tw_dim, tf_dim, tw_dim, -d_dim/2)

        A_total = A_w + A_tf + A_bf
        Qx_total_o = Qx_w_o + Qx_tf_o + Qx_bf_o 
        Qy_total_o = Qy_w_o + Qy_tf_o + Qy_bf_o 
        Ixx_total_o = Ixx_o_w + Ixx_o_tf + Ixx_o_bf
        Iyy_total_o = Iyy_o_w + Iyy_o_tf + Iyy_o_bf
        Ixy_total_o = Ixy_o_w + Ixy_o_tf + Ixy_o_bf

        Xc_o = Qy_total_o / A_total if A_total > 1e-9 else 0 
        Yc_o = Qx_total_o / A_total if A_total > 1e-9 else 0 # Should be ~0

        Ixx_c = Ixx_total_o - A_total * Yc_o**2
        Iyy_c = Iyy_total_o - A_total * Xc_o**2
        Ixy_c = Ixy_total_o - A_total * Xc_o * Yc_o
        
        J_val = (1/3) * (hw_dim * tw_dim**3 + 2 * bf_dim * tf_dim**3) 
        Cw_val = None 
        Zx_val = bf_dim*tf_dim*(d_dim-tf_dim) + tw_dim*hw_dim**2/4 
        Zy_val = None 

        self.properties.update({
            "A": A_total, "Xc": Xc_o, "Yc": Yc_o, 
            "Ixx": Ixx_c, "Iyy": Iyy_c, "Ixy": Ixy_c,
            "y_top": d_dim/2 - Yc_o, "y_bottom": d_dim/2 + Yc_o,
            "x_left": Xc_o, "x_right": bf_dim - Xc_o, 
            "J": J_val, "Cw": Cw_val, "Zx": Zx_val, "Zy": Zy_val
        })

    def _calculate_angle_integration(self):
        L1 = self.input_dims_converted_to_base.get("L1") 
        L2 = self.input_dims_converted_to_base.get("L2") 
        t = self.input_dims_converted_to_base.get("t")   
        
        if None in [L1, L2, t] or L1 <= 0 or L2 <= 0 or t <= 0:
            raise ValueError("L1, L2, t must be positive for Angle section.")
        if t > L1 or t > L2: 
            raise ValueError("Thickness (t) cannot exceed leg lengths (L1, L2) for Angle section.")

        A1, Qx1_o, Qy1_o, Ixx1_o, Iyy1_o, Ixy1_o = \
            self._integrate_rectangle_part(L1, t, 0, 0)
        A2, Qx2_o, Qy2_o, Ixx2_o, Iyy2_o, Ixy2_o = \
            self._integrate_rectangle_part(t, L2 - t, 0, t)
            
        A_total = A1 + A2
        Qx_total_o = Qx1_o + Qx2_o
        Qy_total_o = Qy1_o + Qy2_o
        Ixx_total_o = Ixx1_o + Ixx2_o
        Iyy_total_o = Iyy1_o + Iyy2_o
        Ixy_total_o = Ixy1_o + Ixy2_o
        
        Xc_o = Qy_total_o / A_total if A_total > 1e-9 else 0
        Yc_o = Qx_total_o / A_total if A_total > 1e-9 else 0
        
        Ixx_c = Ixx_total_o - A_total * Yc_o**2
        Iyy_c = Iyy_total_o - A_total * Xc_o**2
        Ixy_c = Ixy_total_o - A_total * Xc_o * Yc_o

        J_val = (1/3) * (L1 * t**3 + (L2-t) * t**3) 
        Cw_val = None 
        Zx_val = None 
        Zy_val = None 

        self.properties.update({
            "A": A_total, "Xc": Xc_o, "Yc": Yc_o, 
            "Ixx": Ixx_c, "Iyy": Iyy_c, "Ixy": Ixy_c,
            "y_top": L2 - Yc_o, "y_bottom": Yc_o, 
            "x_left": Xc_o, "x_right": L1 - Xc_o, 
            "J": J_val, "Cw": Cw_val, "Zx": Zx_val, "Zy": Zy_val
        })

    def _calculate_tee_integration(self):
        d_dim = self.input_dims_converted_to_base.get("d")      
        bf_dim = self.input_dims_converted_to_base.get("bf")    
        tf_dim = self.input_dims_converted_to_base.get("tf")    
        ts_dim = self.input_dims_converted_to_base.get("ts")    
        
        if None in [d_dim, bf_dim, tf_dim, ts_dim] or d_dim <= 0 or bf_dim <= 0 or tf_dim <= 0 or ts_dim <= 0:
            raise ValueError("d, bf, tf, ts must be positive for Tee section.")
        if tf_dim >= d_dim : raise ValueError("Flange thickness (tf) must be less than overall depth (d) for Tee.")
        if ts_dim > bf_dim : raise ValueError("Stem thickness (ts) must not exceed flange width (bf) for Tee.")

        hs_dim = d_dim - tf_dim # stem height

        # Origin: Centerline of stem (x=0), at the bottom of the stem (y=0)
        # Stem part:
        # Bottom-left corner: (-ts_dim/2, 0)
        A_s, Qx_s_o, Qy_s_o, Ixx_o_s, Iyy_o_s, Ixy_o_s = \
            self._integrate_rectangle_part(ts_dim, hs_dim, -ts_dim/2, 0)

        # Flange part:
        # Bottom-left corner: (-bf_dim/2, hs_dim)
        A_f, Qx_f_o, Qy_f_o, Ixx_o_f, Iyy_o_f, Ixy_o_f = \
            self._integrate_rectangle_part(bf_dim, tf_dim, -bf_dim/2, hs_dim)
            
        A_total = A_s + A_f
        Qx_total_o = Qx_s_o + Qx_f_o # This is sum of y*dA, will give Yc_o * A_total
        Qy_total_o = Qy_s_o + Qy_f_o # This is sum of x*dA, should be 0
        Ixx_total_o = Ixx_o_s + Ixx_o_f
        Iyy_total_o = Iyy_o_s + Iyy_o_f
        Ixy_total_o = Ixy_o_s + Ixy_o_f # Should be 0

        Xc_o = Qy_total_o / A_total if A_total > 1e-9 else 0 # Should be 0
        Yc_o = Qx_total_o / A_total if A_total > 1e-9 else 0 # This is Yc from bottom of stem

        Ixx_c = Ixx_total_o - A_total * Yc_o**2
        Iyy_c = Iyy_total_o - A_total * Xc_o**2
        Ixy_c = Ixy_total_o - A_total * Xc_o * Yc_o # Should be 0
        
        J_val = (1/3) * (bf_dim * tf_dim**3 + hs_dim * ts_dim**3) 
        Cw_val = 0 
        Zx_val = None 
        Zy_val = None

        self.properties.update({
            "A": A_total, "Xc": Xc_o, "Yc": Yc_o, # Xc_o is 0, Yc_o is from bottom of stem
            "Ixx": Ixx_c, "Iyy": Iyy_c, "Ixy": Ixy_c,
            "y_top": d_dim - Yc_o, "y_bottom": Yc_o,
            "x_left": bf_dim/2, "x_right": bf_dim/2,
            "J": J_val, "Cw": Cw_val, "Zx": Zx_val, "Zy": Zy_val
        })

    def _calculate_hss_rectangular_integration(self):
        H_outer = self.input_dims_converted_to_base.get("H") 
        B_outer = self.input_dims_converted_to_base.get("B") 
        t = self.input_dims_converted_to_base.get("t")
        
        if None in [H_outer, B_outer, t] or H_outer <= 0 or B_outer <= 0 or t <= 0:
            raise ValueError("H, B, t must be positive for HSS Rectangular.")
        if 2*t >= H_outer or 2*t >= B_outer: 
            raise ValueError("Thickness (2*t) must be less than H and B for HSS Rectangular.")

        A_outer, Qx_outer_o, Qy_outer_o, Ixx_outer_o, Iyy_outer_o, Ixy_outer_o = \
            self._integrate_rectangle_part(B_outer, H_outer, -B_outer/2, -H_outer/2)

        B_inner = B_outer - 2*t
        H_inner = H_outer - 2*t
        
        A_inner, Qx_inner_o, Qy_inner_o, Ixx_inner_o, Iyy_inner_o, Ixy_inner_o = (0,0,0,0,0,0)
        if B_inner > 1e-9 and H_inner > 1e-9: 
            A_inner, Qx_inner_o, Qy_inner_o, Ixx_inner_o, Iyy_inner_o, Ixy_inner_o = \
                self._integrate_rectangle_part(B_inner, H_inner, -B_inner/2, -H_inner/2)

        A_net = A_outer - A_inner
        Qx_net_o = Qx_outer_o - Qx_inner_o 
        Qy_net_o = Qy_outer_o - Qy_inner_o 
        Ixx_net_o = Ixx_outer_o - Ixx_inner_o
        Iyy_net_o = Iyy_outer_o - Iyy_inner_o
        Ixy_net_o = Ixy_outer_o - Ixy_inner_o 
        
        Xc_net = Qy_net_o / A_net if A_net > 1e-9 else 0 # Should be 0
        Yc_net = Qx_net_o / A_net if A_net > 1e-9 else 0 # Should be 0
        
        Ixx_c = Ixx_net_o - A_net * Yc_net**2
        Iyy_c = Iyy_net_o - A_net * Xc_net**2
        Ixy_c = Ixy_net_o - A_net * Xc_net * Yc_net

        Am = (B_outer-t)*(H_outer-t) 
        pm = 2*((B_outer-t) + (H_outer-t)) 
        J_val = (4 * Am**2 * t) / pm if pm > 1e-9 else 0
        Cw_val = 0
        
        Zx_val = B_outer*H_outer**2/4 - (B_inner)*(H_inner)**2/4
        Zy_val = H_outer*B_outer**2/4 - (H_inner)*(B_inner)**2/4

        self.properties.update({
            "A": A_net, "Xc": Xc_net, "Yc": Yc_net,
            "Ixx": Ixx_c, "Iyy": Iyy_c, "Ixy": Ixy_c,
            "y_top": H_outer/2 - Yc_net, "y_bottom": H_outer/2 + Yc_net, 
            "x_left": B_outer/2 + Xc_net, "x_right": B_outer/2 - Xc_net,
            "J": J_val, "Cw": Cw_val, "Zx": Zx_val, "Zy": Zy_val
        })

    def _calculate_hss_circular_integration(self):
        OD = self.input_dims_converted_to_base.get("OD")
        t = self.input_dims_converted_to_base.get("t")
        if None in [OD, t] or OD <= 0 or t <= 0:
            raise ValueError("OD and t must be positive for HSS Circular.")
        if 2*t >= OD: raise ValueError("Thickness (2*t) must be less than Outer Diameter (OD) for HSS Circular.")

        R_outer = OD / 2
        ID_val = OD - 2*t # Renamed to avoid conflict with global ID
        R_inner = ID_val / 2

        A_outer, Qx_outer_o, Qy_outer_o, Ixx_o_outer, Iyy_o_outer, Ixy_o_outer, J_outer = \
            self._integrate_solid_circular_part(R_outer)
        A_inner, Qx_inner_o, Qy_inner_o, Ixx_o_inner, Iyy_o_inner, Ixy_o_inner, J_inner = \
            self._integrate_solid_circular_part(R_inner)
            
        A_net = A_outer - A_inner
        Qx_net_o = Qx_outer_o - Qx_inner_o 
        Qy_net_o = Qy_outer_o - Qy_inner_o 
        Ixx_net_o = Ixx_o_outer - Ixx_o_inner
        Iyy_net_o = Iyy_o_outer - Iyy_o_inner
        Ixy_net_o = Ixy_o_outer - Ixy_o_inner 
        J_net = J_outer - J_inner
        
        Xc_net = Qy_net_o / A_net if A_net > 1e-9 else 0 # Should be 0
        Yc_net = Qx_net_o / A_net if A_net > 1e-9 else 0 # Should be 0
        
        Ixx_c = Ixx_net_o - A_net * Yc_net**2
        Iyy_c = Iyy_net_o - A_net * Xc_net**2
        Ixy_c = Ixy_net_o - A_net * Xc_net * Yc_net # Should be 0

        Zx_val = (OD**3 - ID_val**3) / 6
        Zy_val = Zx_val

        self.properties.update({
            "A": A_net, "Xc": Xc_net, "Yc": Yc_net,
            "Ixx": Ixx_c, "Iyy": Iyy_c, "Ixy": Ixy_c,
            "y_top": OD/2 - Yc_net, "y_bottom": OD/2 + Yc_net, 
            "x_left": OD/2 + Xc_net, "x_right": OD/2 - Xc_net,
            "J": J_net, "Cw": 0, 
            "Zx": Zx_val, "Zy": Zy_val
        })

    def calculate_properties(self):
        if self.section_data_from_lib and self.standard_code == "INDIAN_SP6":
            # For INDIAN_SP6, dimensions and Area are loaded. Calculate other geometric props.
            if self.shape_type == "SolidRectangle": self._calculate_solid_rectangle_integration()
            elif self.shape_type == "I-Beam": self._calculate_i_beam_integration()
            elif self.shape_type == "SolidCircle": self._calculate_solid_circle_integration()
            elif self.shape_type == "Channel": self._calculate_channel_integration()
            elif self.shape_type == "Angle": self._calculate_angle_integration()
            elif self.shape_type == "Tee": self._calculate_tee_integration()
            elif self.shape_type == "HSS-Rectangular": self._calculate_hss_rectangular_integration()
            elif self.shape_type == "HSS-Circular": self._calculate_hss_circular_integration()
            # Note: _calculate_..._integration methods update self.properties with Ixx, J, etc.
            # They also set y_top, y_bottom etc. based on the dimensions.
            # Area (A) was already loaded from library for SP6.
        elif self.shape_type == "I-Beam" and self.section_data_from_lib and self.standard_code != "INDIAN_SP6":
            # For non-SP6 library I-Beams, if J was not loaded (e.g. old library format or specific exclusion)
            # then calculate it. This maintains previous logic for non-SP6 I-Beams.
            if "J" not in self.properties or self.properties["J"] is None:
                 self._calculate_i_beam_integration() # This will calculate J and other props like Zx, Zy

        # For manual input, _process_manual_dims already called the specific _calculate_..._integration method.
        # For library sections (non-SP6), most properties are loaded directly in _load_from_library.

        self._calculate_general_properties()

# --- Flask App Setup ---
app = Flask(__name__)
calculator_app_instance = None

def get_calculator_app():
    global calculator_app_instance
    if calculator_app_instance is None:
        calculator_app_instance = SectionCalculatorApp()
    return calculator_app_instance

class SectionCalculatorApp:
    def __init__(self):
        self.unit_system_obj = UnitSystem()
        self.section_library = self._load_section_library("section_library.json")
        self.current_section = None
        self.section_type_name = None

    def _load_section_library(self, filepath):
        try:
            with open(filepath, 'r') as f: library = json.load(f)
            return library
        except FileNotFoundError: return {}
        except json.JSONDecodeError: return {}

    def set_unit_system(self, system_name): self.unit_system_obj.set_system(system_name)
    def set_section_type(self, section_type_name_str): self.section_type_name = section_type_name_str

    def define_standard_section_from_library(self, standard_code, shape_type, designation):
        if not self.section_type_name == "StandardRolled": raise ValueError("Section type must be 'StandardRolled'")
        try:
            section_data_list = self.section_library[standard_code][shape_type]
            section_data = next(s for s in section_data_list if s["designation"] == designation)
            self.current_section = StandardRolledSection(self.unit_system_obj, shape_type, standard_code=standard_code, section_data=section_data)
        except (KeyError, StopIteration): raise ValueError(f"Section {designation} not found.")

    def define_standard_section_manual(self, shape_type, dims):
        if not self.section_type_name == "StandardRolled": raise ValueError("Section type must be 'StandardRolled'")
        self.current_section = StandardRolledSection(self.unit_system_obj, shape_type, standard_code=None, manual_dims=dims)

    def calculate(self):
        if self.current_section:
            self.current_section.calculate_properties()
            return self.current_section.get_properties_in_display_units()
        else: raise ValueError("No section defined.")

@app.route('/')
def index(): return render_template('index.html')

@app.route('/get_library_data')
def get_library_data_route(): return jsonify(get_calculator_app().section_library)

@app.route('/calculate', methods=['POST'])
def calculate_route():
    data = request.get_json()
    app_logic = get_calculator_app()
    try:
        app_logic.set_unit_system(data['unit_system'])
        app_logic.set_section_type(data['section_type'])
        inputs = data['inputs']
        if data['section_type'] == 'StandardRolled':
            if inputs['method'] == 'Manual': app_logic.define_standard_section_manual(inputs['shape_type'], inputs['dimensions'])
            elif inputs['method'] == 'Library': app_logic.define_standard_section_from_library(inputs['standard_code'], inputs['shape_type'], inputs['designation'])
        else: return jsonify({"error": "Section type not fully implemented."}), 400
        return jsonify({"results": app_logic.calculate()})
    except Exception as e:
        print(f"Error in /calculate: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/export_excel', methods=['POST'])
def export_excel_route():
    data = request.get_json()
    app_logic = get_calculator_app()
    try:
        app_logic.set_unit_system(data['unit_system'])
        app_logic.set_section_type(data['section_type'])
        inputs = data['inputs']
        if data['section_type'] == 'StandardRolled':
            if inputs['method'] == 'Manual': app_logic.define_standard_section_manual(inputs['shape_type'], inputs['dimensions'])
            elif inputs['method'] == 'Library': app_logic.define_standard_section_from_library(inputs['standard_code'], inputs['shape_type'], inputs['designation'])
        else: return jsonify({"error": "Excel export for this type not implemented."}), 400
        
        results_data = app_logic.calculate() # results_data is a dict of dicts
        
        workbook = openpyxl.Workbook()
        
        # --- Input Parameters Sheet ---
        input_sheet = workbook.active 
        input_sheet.title = "Input Parameters"
        input_sheet.append(["Parameter", "Value", "Unit"])
        
        input_sheet.append(["Unit System", data.get('unit_system'), ""])
        input_sheet.append(["Section Type", data.get('section_type'), ""])
        
        section_inputs = data.get('inputs', {})
        input_sheet.append(["Input Method", section_inputs.get('method'), ""])

        length_unit_symbol = app_logic.unit_system_obj.get_display_unit_symbol("length")

        if section_inputs.get('method') == 'Manual':
            input_sheet.append(["Shape Type", section_inputs.get('shape_type'), ""])
            dimensions = section_inputs.get('dimensions', {})
            for dim_key, dim_val_list in dimensions.items():
                full_name = PROPERTY_NAME_MAP.get(dim_key, dim_key)
                input_sheet.append([f"{full_name} ({dim_key})", dim_val_list[0], length_unit_symbol])
        elif section_inputs.get('method') == 'Library':
            input_sheet.append(["Standard Code", section_inputs.get('standard_code'), ""])
            input_sheet.append(["Shape Type", section_inputs.get('shape_type'), ""])
            input_sheet.append(["Designation", section_inputs.get('designation'), ""])

        # --- Section Properties Sheet ---
        props_sheet = workbook.create_sheet("Section Properties")
        props_sheet.append(["Description", "Symbol", "Value", "Unit"]) 
        for key_symbol, data_dict_item in results_data.items():
            name = data_dict_item.get("name", key_symbol)
            value = data_dict_item.get("value")
            unit = data_dict_item.get("unit", "")
            
            processed_value = value
            if isinstance(value, float):
                processed_value = float(f"{value:.4f}") # Format float, then convert back to float for Excel type
            
            if processed_value is None:
                 processed_value = "N/A"
            
            props_sheet.append([name, key_symbol, processed_value, unit])
        
        excel_stream = BytesIO()
        workbook.save(excel_stream)
        excel_stream.seek(0)
        return send_file(excel_stream, as_attachment=True, download_name="section_properties.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        print(f"Excel export error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": "Failed to generate Excel file."}), 500

# gcloud init
