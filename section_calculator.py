# section_calculator.py
# Main application file for the Sectional Properties Calculator

import math
import json
from flask import Flask, render_template, request, jsonify, send_file
from io import BytesIO  
import openpyxl

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
    def __init__(self, unit_system_obj, shape_type, section_data=None, manual_dims=None):
        super().__init__(unit_system_obj)
        self.shape_type = shape_type
        self.section_data_from_lib = section_data 
        self.manual_dims_input = manual_dims 

        if self.section_data_from_lib:
            self._load_from_library()
        elif self.manual_dims_input:
            self._process_manual_dims()
        else:
            raise ValueError("Either section_data (library) or manual_dims must be provided.")

    def _load_from_library(self):
        self.properties["A"] = self.section_data_from_lib.get("A_base")
        self.properties["Ixx"] = self.section_data_from_lib.get("Ixx_base")
        self.properties["Iyy"] = self.section_data_from_lib.get("Iyy_base")
        self.properties["Ixy"] = self.section_data_from_lib.get("Ixy_base", 0)
        self.properties["J"] = self.section_data_from_lib.get("J_base")
        self.properties["Cw"] = self.section_data_from_lib.get("Cw_base")
        self.properties["Zx"] = self.section_data_from_lib.get("Zx_base") 
        self.properties["Zy"] = self.section_data_from_lib.get("Zy_base")
        self.properties["Xc"] = 0 
        self.properties["Yc"] = 0
        d_base = self.section_data_from_lib.get("d_base")
        bf_base = self.section_data_from_lib.get("bf_base")
        od_base = self.section_data_from_lib.get("OD_base", self.section_data_from_lib.get("D_base"))
        h_rect_base = self.section_data_from_lib.get("H_base", self.section_data_from_lib.get("h_base"))
        b_rect_base = self.section_data_from_lib.get("B_base", self.section_data_from_lib.get("b_base"))

        if d_base: 
            self.properties["y_top"], self.properties["y_bottom"] = d_base / 2, d_base / 2
        elif od_base: 
             self.properties["y_top"], self.properties["y_bottom"] = od_base / 2, od_base / 2
        elif h_rect_base: 
            self.properties["y_top"], self.properties["y_bottom"] = h_rect_base / 2, h_rect_base / 2
        
        if bf_base: 
            self.properties["x_left"], self.properties["x_right"] = bf_base / 2, bf_base / 2
        elif od_base: 
            self.properties["x_left"], self.properties["x_right"] = od_base / 2, od_base / 2
        elif b_rect_base: 
            self.properties["x_left"], self.properties["x_right"] = b_rect_base / 2, b_rect_base / 2
            
        self.input_dims = self.section_data_from_lib.get("dimensions_display", {})

    def _process_manual_dims(self):
        self.input_dims_converted_to_base = self._convert_inputs_to_base(self.manual_dims_input)
        if self.shape_type == "SolidRectangle": self._calculate_solid_rectangle()
        elif self.shape_type == "I-Beam": self._calculate_i_beam()
        elif self.shape_type == "SolidCircle": self._calculate_solid_circle()
        elif self.shape_type == "Channel": self._calculate_channel()
        elif self.shape_type == "Angle": self._calculate_angle()
        elif self.shape_type == "Tee": self._calculate_tee()
        elif self.shape_type == "HSS-Rectangular": self._calculate_hss_rectangular()
        elif self.shape_type == "HSS-Circular": self._calculate_hss_circular()
        else: raise NotImplementedError(f"Manual calculation for {self.shape_type} not yet implemented.")

    def _calculate_solid_rectangle(self):
        b = self.input_dims_converted_to_base.get("b") 
        h = self.input_dims_converted_to_base.get("h") 
        if b is None or h is None: raise ValueError("Width (b) and Height (h) must be provided.")
        if b <=0 or h <=0: raise ValueError("Dimensions must be positive.")
        self.properties.update({
            "A": b * h, "Xc": 0, "Yc": 0, "Ixx": (b * h**3)/12, "Iyy": (h * b**3)/12, "Ixy": 0,
            "y_top": h/2, "y_bottom": h/2, "x_left": b/2, "x_right": b/2,
            "J": (1/3) * (1 - 0.63 * (min(b,h)/max(b,h)) + 0.052 * (min(b,h)/max(b,h))**5) * max(b,h) * min(b,h)**3 if max(b,h) > 0 else 0,
            "Cw": 0, "Zx": (b * h**2)/4, "Zy": (h * b**2)/4
        })

    def _calculate_i_beam(self):
        d = self.input_dims_converted_to_base.get("d")      
        bf = self.input_dims_converted_to_base.get("bf")    
        tf = self.input_dims_converted_to_base.get("tf")    
        tw = self.input_dims_converted_to_base.get("tw")    
        if None in [d, bf, tf, tw]: raise ValueError("d, bf, tf, tw must be provided.")
        if d <=0 or bf <=0 or tf <=0 or tw <=0: raise ValueError("Dimensions must be positive.")
        hw = d - 2 * tf 
        if hw <= 0 : raise ValueError("Web height (d - 2*tf) must be positive.")
        area_flange, area_web = bf * tf, hw * tw
        Ixx_flanges = 2 * ((bf * tf**3 / 12) + area_flange * ((d - tf) / 2)**2)
        Iyy_flanges = 2 * (tf * bf**3 / 12)
        Iyy_val = Iyy_flanges + (hw * tw**3)/12
        self.properties.update({
            "A": 2 * area_flange + area_web, "Xc": 0, "Yc": 0,
            "Ixx": Ixx_flanges + (tw * hw**3)/12, "Iyy": Iyy_val, "Ixy": 0,
            "y_top": d/2, "y_bottom": d/2, "x_left": bf/2, "x_right": bf/2,
            "J": (1/3) * (2 * bf * tf**3 + hw * tw**3),
            "Cw": Iyy_val * ((d - tf)**2) / 4 if Iyy_val else 0,
            "Zx": (bf * tf * (d - tf)) + (tw * hw**2 / 4),
            "Zy": (tf * bf**2 / 2) + (hw * tw**2 / 4)
        })

    def _calculate_solid_circle(self):
        D = self.input_dims_converted_to_base.get("D")
        if D is None or D <= 0: raise ValueError("Diameter (D) must be positive.")
        A = PI * D**2 / 4
        Ixx = PI * D**4 / 64
        Iyy = Ixx
        J = PI * D**4 / 32
        Zx = D**3 / 6
        Zy = Zx
        self.properties.update({
            "A": A, "Xc": 0, "Yc": 0, "Ixx": Ixx, "Iyy": Iyy, "Ixy": 0,
            "y_top": D/2, "y_bottom": D/2, "x_left": D/2, "x_right": D/2,
            "J": J, "Cw": 0, "Zx": Zx, "Zy": Zy
        })

    def _calculate_channel(self):
        d = self.input_dims_converted_to_base.get("d")
        bf = self.input_dims_converted_to_base.get("bf") # Overall flange width
        tf = self.input_dims_converted_to_base.get("tf")
        tw = self.input_dims_converted_to_base.get("tw")
        if None in [d, bf, tf, tw] or d <= 0 or bf <= 0 or tf <= 0 or tw <= 0:
            raise ValueError("d, bf, tf, tw must be positive.")
        if bf <= tw: raise ValueError("Flange width (bf) must be greater than web thickness (tw).")
        if d <= 2*tf: raise ValueError("Overall depth (d) must be greater than twice flange thickness (2*tf).")

        hw = d - 2*tf # web height clear
        
        area_web = hw * tw
        area_one_flange = bf * tf
        A = area_web + 2 * area_one_flange

        # Centroid Xc from the back of the web
        Xc = (area_web * (tw/2) + 2 * area_one_flange * (bf/2)) / A
        Yc = 0 # Symmetric about x-axis

        # Moment of inertia about centroidal axes
        Ixx_web_local = (tw * hw**3) / 12
        Ixx_flange_local = (bf * tf**3) / 12
        Ixx = Ixx_web_local + 2 * (Ixx_flange_local + area_one_flange * ((d-tf)/2)**2)
        
        Iyy_web_local = (hw * tw**3) / 12
        Iyy_flange_local = (tf * bf**3) / 12
        Iyy = (Iyy_web_local + area_web * (Xc - tw/2)**2) + \
              2 * (Iyy_flange_local + area_one_flange * (bf/2 - Xc)**2)

        J = (1/3) * (hw * tw**3 + 2 * bf * tf**3) # Approximation

        # Plastic section modulus (approximate for symmetric bending)
        # PNA for Zx is at d/2.
        Zx = bf*tf*(d-tf) + tw*hw**2/4
        Zy = None # Complex for channel, not typically required for simple manual input

        self.properties.update({
            "A": A, "Xc": Xc, "Yc": Yc, "Ixx": Ixx, "Iyy": Iyy, "Ixy": 0,
            "y_top": d/2, "y_bottom": d/2, "x_left": Xc, "x_right": bf - Xc,
            "J": J, "Cw": None, # Cw is complex for channels
            "Zx": Zx, "Zy": Zy
        })

    def _calculate_angle(self):
        L1 = self.input_dims_converted_to_base.get("L1")
        L2 = self.input_dims_converted_to_base.get("L2")
        t = self.input_dims_converted_to_base.get("t")
        if None in [L1, L2, t] or L1 <= 0 or L2 <= 0 or t <= 0:
            raise ValueError("L1, L2, t must be positive.")
        if t > L1 or t > L2: raise ValueError("Thickness (t) cannot exceed leg lengths (L1, L2).")

        A = (L1 + L2 - t) * t
        # Centroid from outer corner (origin at intersection of outer faces of L1 and L2)
        Xc_corner = (L1**2 * t + (L2 - t) * t**2) / (2 * A)
        Yc_corner = (L2**2 * t + (L1 - t) * t**2) / (2 * A)
        
        # Properties about axes through centroid, parallel to legs
        # Ix'x' (about axis through centroid parallel to L1)
        Ixx_c = (t*L2**3)/3 + (L1-t)*t**3/3 - A*Yc_corner**2
        # Iy'y' (about axis through centroid parallel to L2)
        Iyy_c = (L2*t**3)/3 + (L1-t)*t**3/3 - A*Xc_corner**2 # Error in formula, should be L1^3 for Iyy
        Iyy_c = (t*L1**3)/3 + (L2-t)*t**3/3 - A*Xc_corner**2


        # Product of inertia Ixy_c about centroidal axes parallel to legs
        # For simplicity, using a known formula for equal legs and adapting
        # Ixy_c for L-section with origin at centroid, axes parallel to legs:
        # Ixy_c = (+/-) t^2 * (L1-t) * (L2-t) / 4  -- sign depends on quadrant
        # A more general approach is needed or use tabulated values for Ixy if available
        # For manual input, Ixy calculation is complex.
        # Let's calculate Ixy about corner axes first, then transfer.
        # Ixy_o (about corner axes parallel to legs)
        # For leg L1 along X, L2 along Y:
        # Ixy_o = integral(xy dA) = integral_0^t integral_0^L1 (x*y dx dy) for L1 part
        #         + integral_0^L2 integral_0^t (x*y dy dx) for L2 part (careful with limits)
        # Simpler: Ixy_o = (L1*t * (L1/2) * (t/2)) + ((L2-t)*t * (t/2) * (t + (L2-t)/2))
        Ixy_o = (L1*t * (L1/2) * (t/2)) + (t*(L2-t) * (t/2) * ( (L2-t)/2 + t) ) # This is not right
        # From first principles, for origin at outer corner:
        # Rectangle 1 (L1xt): centroid (L1/2, t/2), Area1 = L1*t
        # Rectangle 2 ((L2-t)xt): centroid (t/2, t+(L2-t)/2), Area2 = (L2-t)*t
        # Ixy_o = Ixy_c1 + A1*d1x*d1y + Ixy_c2 + A2*d2x*d2y. Ixy_c1, Ixy_c2 = 0 for rectangles.
        # d1x = L1/2, d1y = t/2
        # d2x = t/2, d2y = t + (L2-t)/2 = (L2+t)/2
        Ixy_o = (L1*t * (L1/2) * (t/2)) + ((L2-t)*t * (t/2) * ((L2+t)/2) )
        Ixy_c = Ixy_o - A * Xc_corner * Yc_corner


        J = (1/3) * (L1*t**3 + (L2-t)*t**3) # Approximation for thin legs

        self.properties.update({
            "A": A, "Xc": Xc_corner, "Yc": Yc_corner, # These are distances from corner, not centroid of section itself
            "Ixx": Ixx_c, "Iyy": Iyy_c, "Ixy": Ixy_c,
            "y_top": L2 - Yc_corner, "y_bottom": Yc_corner, 
            "x_left": Xc_corner, "x_right": L1 - Xc_corner,
            "J": J, "Cw": None, "Zx": None, "Zy": None # Zx, Zy, Cw complex for angles
        })
        # Note: Xc, Yc here are from the outer corner. The _calculate_general_properties will use these
        # and Ixx, Iyy, Ixy which are already about the centroid.
        # We need to provide y_top, y_bottom etc. relative to the centroid for Sx, Sy.
        # The current Ixx_c, Iyy_c, Ixy_c are about the centroid.
        # So, y_top for Sx should be max distance from centroid to top fiber along Y.
        # y_top = L2 - Yc_corner; y_bottom = Yc_corner (distances from centroid to extreme fibers)
        # x_left = Xc_corner; x_right = L1 - Xc_corner (distances from centroid to extreme fibers)
        # This needs careful handling of centroid location vs extreme fiber distances.
        # For now, the Xc, Yc stored are from corner. General props will calculate principal axes.

    def _calculate_tee(self):
        d = self.input_dims_converted_to_base.get("d")      # Overall depth
        bf = self.input_dims_converted_to_base.get("bf")    # Flange width
        tf = self.input_dims_converted_to_base.get("tf")    # Flange thickness
        ts = self.input_dims_converted_to_base.get("ts")    # Stem thickness
        if None in [d, bf, tf, ts] or d <= 0 or bf <= 0 or tf <= 0 or ts <= 0:
            raise ValueError("d, bf, tf, ts must be positive.")
        if tf >= d : raise ValueError("Flange thickness (tf) must be less than overall depth (d).")
        if ts > bf : raise ValueError("Stem thickness (ts) must not exceed flange width (bf).")

        area_flange = bf * tf
        hs = d - tf # stem height
        area_stem = hs * ts
        A = area_flange + area_stem

        # Yc from bottom of stem
        Yc = (area_stem * (hs/2) + area_flange * (hs + tf/2)) / A
        Xc = 0 # Symmetric about y-axis

        # Moment of inertia about centroidal axes
        Ixx_flange_local = (bf * tf**3) / 12
        Ixx_stem_local = (ts * hs**3) / 12
        Ixx = (Ixx_flange_local + area_flange * (hs + tf/2 - Yc)**2) + \
              (Ixx_stem_local + area_stem * (hs/2 - Yc)**2)
        
        Iyy = (tf * bf**3) / 12 + (hs * ts**3) / 12
        
        J = (1/3) * (bf * tf**3 + hs * ts**3) # Approximation
        
        self.properties.update({
            "A": A, "Xc": Xc, "Yc": Yc, # Yc is from bottom of stem
            "Ixx": Ixx, "Iyy": Iyy, "Ixy": 0,
            "y_top": d - Yc, "y_bottom": Yc, 
            "x_left": bf/2, "x_right": bf/2,
            "J": J, "Cw": 0, # Cw approx 0 for symmetric tee
            "Zx": None, "Zy": None # Zx, Zy complex for Tee PNA
        })
        # Note: Yc is from bottom. y_top/y_bottom are distances from centroid.

    def _calculate_hss_rectangular(self):
        H = self.input_dims_converted_to_base.get("H") # Overall Height
        B = self.input_dims_converted_to_base.get("B") # Overall Width
        t = self.input_dims_converted_to_base.get("t")
        if None in [H, B, t] or H <= 0 or B <= 0 or t <= 0:
            raise ValueError("H, B, t must be positive.")
        if 2*t >= H or 2*t >= B: raise ValueError("Thickness (2*t) must be less than H and B.")

        A = B*H - (B - 2*t)*(H - 2*t)
        Ixx = (B*H**3 - (B - 2*t)*(H - 2*t)**3) / 12
        Iyy = (H*B**3 - (H - 2*t)*(B - 2*t)**3) / 12
        
        # J approx for thin-walled closed sections (Bredt's)
        Am = (B-t)*(H-t) # Mean enclosed area
        pm = 2*((B-t) + (H-t)) # Mean perimeter
        J = (4 * Am**2 * t) / pm if pm > 0 else 0 # Simplified Bredt's
        # More accurate J for SHS/RHS often uses specific formulas or tables.
        # For now, using a common approximation: J = t*(H-t)*(B-t)*(H-t+B-t) / ((H-t)+(B-t)) * 2 -- No
        # J = ( (H-t)**3 * (B-t) + (B-t)**3 * (H-t) + t**4 * (H-t+B-t)/2 ) * t / 3 -- No
        # Using sum of (1/3)bt^3 for components is not good for closed sections.
        # Let's use a simpler sum of components for now, acknowledging it's a rough approx for J.
        # J_approx = (1/3) * (2*B*t**3 + 2*(H-2*t)*t**3)
        # A better approx for thin tubes: J = 2*t*(B-t)*(H-t)
        # Using the formula from AISC Design Guide 9 (approx, ignoring corner radii):
        # J = t * (B-t)**3 / 3 + t * (H-t)**3 / 3 + (B-t) * (H-t) * t * (B-t + H-t) / 3 -- No
        # J = (t * (B-t)**3 + t * (H-2*t)**3 + (B-2*t)*t**3 * 2 ) / 3 -- No
        # Let's use the one from provided SHS CSV data if possible, or a known approx.
        # For manual, we need a formula. J from AISC DG9: J = 2*t*(B-t)*(H-t) - 4.5*(4-PI)*t^3 (approx)
        # For simplicity and consistency with some texts: J = (2*t*(B-t)*(H-t)**2 + 2*t*(H-t)*(B-t)**2) / ((B-t)+(H-t)) -- No
        # Let's use the formula for J from the provided CSV for SHS if it's consistent or a simple one.
        # The CSV has J values. For manual calculation, a common approx:
        J = 2 * t * (B-t) * (H-t) # Area enclosed by centerline * 2t (approx)

        Zx = B*H**2/4 - (B-2*t)*(H-2*t)**2/4
        Zy = H*B**2/4 - (H-2*t)*(B-2*t)**2/4

        self.properties.update({
            "A": A, "Xc": 0, "Yc": 0, "Ixx": Ixx, "Iyy": Iyy, "Ixy": 0,
            "y_top": H/2, "y_bottom": H/2, "x_left": B/2, "x_right": B/2,
            "J": J, "Cw": 0, "Zx": Zx, "Zy": Zy
        })

    def _calculate_hss_circular(self):
        OD = self.input_dims_converted_to_base.get("OD")
        t = self.input_dims_converted_to_base.get("t")
        if None in [OD, t] or OD <= 0 or t <= 0:
            raise ValueError("OD and t must be positive.")
        if 2*t >= OD: raise ValueError("Thickness (2*t) must be less than Outer Diameter (OD).")

        ID = OD - 2*t
        A = PI/4 * (OD**2 - ID**2)
        Ixx = PI/64 * (OD**4 - ID**4)
        Iyy = Ixx
        J = PI/32 * (OD**4 - ID**4)
        Zx = (OD**3 - ID**3) / 6
        Zy = Zx

        self.properties.update({
            "A": A, "Xc": 0, "Yc": 0, "Ixx": Ixx, "Iyy": Iyy, "Ixy": 0,
            "y_top": OD/2, "y_bottom": OD/2, "x_left": OD/2, "x_right": OD/2,
            "J": J, "Cw": 0, "Zx": Zx, "Zy": Zy
        })

    def calculate_properties(self):
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
            self.current_section = StandardRolledSection(self.unit_system_obj, shape_type, section_data=section_data)
        except (KeyError, StopIteration): raise ValueError(f"Section {designation} not found.")

    def define_standard_section_manual(self, shape_type, dims):
        if not self.section_type_name == "StandardRolled": raise ValueError("Section type must be 'StandardRolled'")
        self.current_section = StandardRolledSection(self.unit_system_obj, shape_type, manual_dims=dims)

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
