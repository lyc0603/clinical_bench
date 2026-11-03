"""Original gates with a value-preserving nullable-string inspection view."""
import pandas as pd
from gxp_full.checks import node_checks as original_node_checks


def node_checks(frame,*args,**kwargs):
    # pandas 2.2 maps an empty nullable-string series back to string dtype;
    # its .all() reduction then raises. Inspect an object view of declared
    # string extension columns, preserving every value and missing marker.
    inspection=frame.copy()
    for name in inspection:
        if isinstance(inspection[name].dtype,pd.StringDtype):inspection[name]=inspection[name].astype(object)
    return original_node_checks(inspection,*args,**kwargs)
