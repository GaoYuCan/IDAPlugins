from __future__ import division
from __future__ import print_function
from struct import unpack

# this plugin requires IDA 7.4 or newer
try:
    import idaapi
    import idautils
    import idc
    import ida_pro
    SUPPORTED_IDA = ida_pro.IDA_SDK_VERSION >= 740

    if ida_pro.IDA_SDK_VERSION >= 920:
        from PySide6.QtWidgets import QApplication
    else:
        from PyQt5.Qt import QApplication
except Exception as e:
    print(e)
    SUPPORTED_IDA = False

# is this deemed to be a compatible environment for the plugin to load?
if not SUPPORTED_IDA:
    print("LazyIDA plugin is not compatible with this IDA version")

ACTION_CONVERT = ["lazyida:convert%d" % i for i in range(10)]
ACTION_COPYEA = "lazyida:copyea"
ACTION_COPYFO = "lazyida:copyfo"
ACTION_GOTOCLIPEA = "lazyida:gotoclipea"
ACTION_GOTOCLIPFO = "lazyida:gotoclipfo"
ACTION_XORDATA = "lazyida:xordata"

ACTION_HX_REMOVERETTYPE = "lazyida:hx_removerettype"
ACTION_HX_COPYEA = "lazyida:hx_copyea"
ACTION_HX_COPYFO = "lazyida:hx_copyfo"
ACTION_HX_COPYNAME = "lazyida:hx_copyname"
ACTION_HX_GOTOCLIPEA = "lazyida:hx_gotoclipea"
ACTION_HX_GOTOCLIPFO = "lazyida:hx_gotoclipfo"

u16 = lambda x: unpack("<H", x)[0]
u32 = lambda x: unpack("<I", x)[0]
u64 = lambda x: unpack("<Q", x)[0]

ARCH = 0
BITS = 0

def copy_to_clip(data):
    QApplication.clipboard().setText(data)

def clip_text():
    return QApplication.clipboard().text()
    

def parse_location(loc, is_fo=False):
    is_named = False
    ascii_text = ""
    try:
        loc = int(loc, 16)
        if is_fo:
            loc = idaapi.get_fileregion_ea(loc)
    except ValueError:
        try:
            ascii_text = loc.encode(encoding="ascii",errors="replace").decode(encoding="ascii").strip()
            loc = idc.get_name_ea_simple(ascii_text)
            is_named = True
        except:
            return idaapi.BADADDR
    return loc, is_named, ascii_text


class hotkey_action_handler_t(idaapi.action_handler_t):
    """
    Action handler for hotkey actions
    """
    def __init__(self, action):
        idaapi.action_handler_t.__init__(self)
        self.action = action

    def activate(self, ctx):
        if self.action == ACTION_COPYEA:
            ea = idc.get_screen_ea()
            if ea != idaapi.BADADDR:
                copy_to_clip("0x%X" % ea)
                print("Address 0x%X (EA) has been copied to clipboard" % ea)
        elif self.action == ACTION_COPYFO:
            ea = idc.get_screen_ea()
            if ea != idaapi.BADADDR:
                fo = idaapi.get_fileregion_offset(ea)
                if fo != idaapi.BADADDR:
                    copy_to_clip("0x%X" % fo)
                    print("Address 0x%X (FO) has been copied to clipboard" % fo)
        elif self.action == ACTION_GOTOCLIPEA:
            loc, is_named, name = parse_location(clip_text(), False)
            if loc != idaapi.BADADDR:
                if is_named:
                    print("Goto named location '%s' 0x%X" % (name, loc))
                else:
                    print("Goto location 0x%X (EA)" % loc)
                idc.jumpto(loc)
        elif self.action == ACTION_GOTOCLIPFO:
            loc, is_named, name = parse_location(clip_text(), True)
            if loc != idaapi.BADADDR:
                if is_named:
                    print("Goto named location '%s' 0x%X" % (name, loc))
                else:
                    print("Goto location 0x%X (FO)" % idaapi.get_fileregion_offset(loc))
                idc.jumpto(loc)
        return 1

    def update(self, ctx):
        if idaapi.IDA_SDK_VERSION >= 770:
            target_attr = "widget_type"
        else:
            target_attr = "form_type"

        if idaapi.IDA_SDK_VERSION >= 900:
            try:
                dump_type = idaapi.BWN_HEXVIEW
            except:
                dump_type = idaapi.BWN_DUMP
        else:
            dump_type = idaapi.BWN_DUMP

        if ctx.__getattribute__(target_attr) in (idaapi.BWN_DISASM, dump_type):
            return idaapi.AST_ENABLE_FOR_WIDGET
        else:
            return idaapi.AST_DISABLE_FOR_WIDGET

class menu_action_handler_t(idaapi.action_handler_t):
    """
    Action handler for menu actions
    """
    def __init__(self, action):
        idaapi.action_handler_t.__init__(self)
        self.action = action

    def activate(self, ctx):
        if self.action in ACTION_CONVERT:
            # convert (dump as)
            t0, t1, view = idaapi.twinpos_t(), idaapi.twinpos_t(), idaapi.get_current_viewer()
            if idaapi.read_selection(view, t0, t1):
                start, end = t0.place(view).toea(), t1.place(view).toea()
                size = end - start + 1
            elif idc.get_item_size(idc.get_screen_ea()) > 1:
                start = idc.get_screen_ea()
                size = idc.get_item_size(start)
                end = start + size
            else:
                return False

            data = idc.get_bytes(start, size)
            if isinstance(data, str):  # python2 compatibility
                data = bytearray(data)
            name = idc.get_name(start, idc.GN_VISIBLE)
            if not name:
                name = "data"
            if data:
                print("\n[+] Dump 0x%X - 0x%X (%u bytes) :" % (start, end, size))
                if self.action == ACTION_CONVERT[0]:
                    # escaped string
                    output = '"%s"' % "".join("\\x%02X" % b for b in data)
                elif self.action == ACTION_CONVERT[1]:
                    # hex string
                    output = "".join("%02X" % b for b in data)
                elif self.action == ACTION_CONVERT[2]:
                    # C array
                    output = "unsigned char %s[%d] = {" % (name, size)
                    for i in range(size):
                        if i % 16 == 0:
                            output += "\n    "
                        output += "0x%02X, " % data[i]
                    output = output[:-2] + "\n};"
                elif self.action == ACTION_CONVERT[3]:
                    # C array word
                    data += b"\x00"
                    array_size = (size + 1) // 2
                    output = "unsigned short %s[%d] = {" % (name, array_size)
                    for i in range(0, size, 2):
                        if i % 16 == 0:
                            output += "\n    "
                        output += "0x%04X, " % u16(data[i:i+2])
                    output = output[:-2] + "\n};"
                elif self.action == ACTION_CONVERT[4]:
                    # C array dword
                    data += b"\x00" * 3
                    array_size = (size + 3) // 4
                    output = "unsigned int %s[%d] = {" % (name, array_size)
                    for i in range(0, size, 4):
                        if i % 32 == 0:
                            output += "\n    "
                        output += "0x%08X, " % u32(data[i:i+4])
                    output = output[:-2] + "\n};"
                elif self.action == ACTION_CONVERT[5]:
                    # C array qword
                    data += b"\x00" * 7
                    array_size = (size + 7) // 8
                    output = "unsigned long %s[%d] = {" % (name, array_size)
                    for i in range(0, size, 8):
                        if i % 32 == 0:
                            output += "\n    "
                        output += "0x%016X, " % u64(data[i:i+8])
                    output = output[:-2] + "\n};"
                elif self.action == ACTION_CONVERT[6]:
                    # python list
                    output = "[%s]" % ", ".join("0x%02X" % b for b in data)
                elif self.action == ACTION_CONVERT[7]:
                    # python list word
                    data += b"\x00"
                    output = "[%s]" % ", ".join("0x%04X" % u16(data[i:i+2]) for i in range(0, size, 2))
                elif self.action == ACTION_CONVERT[8]:
                    # python list dword
                    data += b"\x00" * 3
                    output = "[%s]" % ", ".join("0x%08X" % u32(data[i:i+4]) for i in range(0, size, 4))
                elif self.action == ACTION_CONVERT[9]:
                    # python list qword
                    data += b"\x00" * 7
                    output = "[%s]" %  ", ".join("%#018X" % u64(data[i:i+8]) for i in range(0, size, 8)).replace("0X", "0x")
                copy_to_clip(output)
                print(output)
        elif self.action == ACTION_XORDATA:
            t0, t1, view = idaapi.twinpos_t(), idaapi.twinpos_t(), idaapi.get_current_viewer()
            if idaapi.read_selection(view, t0, t1):
                start, end = t0.place(view).toea(), t1.place(view).toea()
            else:
                if idc.get_item_size(idc.get_screen_ea()) > 1:
                    start = idc.get_screen_ea()
                    end = start + idc.get_item_size(start)
                else:
                    return False

            data = idc.get_bytes(start, end - start)
            if isinstance(data, str):  # python2 compatibility
                data = bytearray(data)
            x = idaapi.ask_long(0, "Xor with...")
            if x:
                x &= 0xFF
                print("\n[+] Xor 0x%X - 0x%X (%u bytes) with 0x%02X:" % (start, end, end - start, x))
                print(repr("".join(chr(b ^ x) for b in data)))
        else:
            return 0

        return 1

    def update(self, ctx):
        return idaapi.AST_ENABLE_ALWAYS

class hexrays_action_handler_t(idaapi.action_handler_t):
    """
    Action handler for hexrays actions
    """
    def __init__(self, action):
        idaapi.action_handler_t.__init__(self)
        self.action = action
        self.ret_type = {}

    def activate(self, ctx):
        if self.action == ACTION_HX_REMOVERETTYPE:
            vdui = idaapi.get_widget_vdui(ctx.widget)
            self.remove_rettype(vdui)
            vdui.refresh_ctext()
        elif self.action == ACTION_HX_COPYEA:
            ea = idaapi.get_screen_ea()
            if ea != idaapi.BADADDR:
                copy_to_clip("0x%X" % ea)
                print("Address 0x%X (EA) has been copied to clipboard" % ea)
        elif self.action == ACTION_HX_COPYFO:
            ea = idaapi.get_screen_ea()
            if ea != idaapi.BADADDR:
                fo = idaapi.get_fileregion_offset(ea)
                if fo != idaapi.BADADDR:
                    copy_to_clip("0x%X" % fo)
                    print("Address 0x%X (FO) has been copied to clipboard" % fo)
        elif self.action == ACTION_HX_COPYNAME:
            highlight = idaapi.get_highlight(idaapi.get_current_viewer())
            name = highlight[0] if highlight else None
            if name:
                copy_to_clip(name)
                print("'%s' has been copied to clipboard" % name)
        elif self.action == ACTION_HX_GOTOCLIPEA:
            loc, is_named, name = parse_location(clip_text(), False)
            if loc != idaapi.BADADDR:
                if is_named:
                    print("Goto named location '%s' 0x%X" % (name, loc))
                else:
                    print("Goto location 0x%X (EA)" % loc)
                idc.jumpto(loc)
        elif self.action == ACTION_HX_GOTOCLIPFO:
            loc, is_named, name = parse_location(clip_text(), True)
            if loc != idaapi.BADADDR:
                if is_named:
                    print("Goto named location '%s' 0x%X" % (name, loc))
                else:
                    print("Goto location 0x%X (FO)" % idaapi.get_fileregion_offset(loc))
                idc.jumpto(loc)
        else:
            return 0

        return 1

    def update(self, ctx):
        vdui = idaapi.get_widget_vdui(ctx.widget)
        return idaapi.AST_ENABLE_FOR_WIDGET if vdui else idaapi.AST_DISABLE_FOR_WIDGET

    def remove_rettype(self, vu):
        if vu.item.citype == idaapi.VDI_FUNC:
            # current function
            ea = vu.cfunc.entry_ea
            old_func_type = idaapi.tinfo_t()
            if not vu.cfunc.get_func_type(old_func_type):
                return False
        elif vu.item.citype == idaapi.VDI_EXPR and vu.item.e.is_expr() and vu.item.e.type.is_funcptr():
            # call xxx
            ea = vu.item.get_ea()
            old_func_type = idaapi.tinfo_t()

            func = idaapi.get_func(ea)
            if func:
                try:
                    cfunc = idaapi.decompile(func)
                except idaapi.DecompilationFailure:
                    return False

                if not cfunc.get_func_type(old_func_type):
                    return False
            else:
                return False
        else:
            return False

        fi = idaapi.func_type_data_t()
        if ea != idaapi.BADADDR and old_func_type.get_func_details(fi):
            # Return type is already void
            if fi.rettype.is_decl_void():
                # Restore ret type
                if ea not in self.ret_type:
                    return True
                ret = self.ret_type[ea]
            else:
                # Save ret type and change it to void
                self.ret_type[ea] = fi.rettype
                ret = idaapi.BT_VOID

            # Create new function info with new rettype
            fi.rettype = idaapi.tinfo_t(ret)

            # Create new function type with function info
            new_func_type = idaapi.tinfo_t()
            new_func_type.create_func(fi)

            # Apply new function type
            if idaapi.apply_tinfo(ea, new_func_type, idaapi.TINFO_DEFINITE):
                return vu.refresh_view(True)

        return False

class UI_Hook(idaapi.UI_Hooks):
    def __init__(self):
        idaapi.UI_Hooks.__init__(self)

    def finish_populating_widget_popup(self, form, popup):
        form_type = idaapi.get_widget_type(form)

        if idaapi.IDA_SDK_VERSION >= 900:
            try:
                dump_type = idaapi.BWN_HEXVIEW
            except:
                dump_type = idaapi.BWN_DUMP
        else:
            dump_type = idaapi.BWN_DUMP

        if form_type == idaapi.BWN_DISASM or form_type == dump_type:
            t0, t1, view = idaapi.twinpos_t(), idaapi.twinpos_t(), idaapi.get_current_viewer()
            if idaapi.read_selection(view, t0, t1) or idc.get_item_size(idc.get_screen_ea()) > 1:
                idaapi.attach_action_to_popup(form, popup, ACTION_XORDATA, None)
                for action in ACTION_CONVERT:
                    idaapi.attach_action_to_popup(form, popup, action, "Dump/")



class HexRays_Hook(object):
    def callback(self, event, *args):
        if event == idaapi.hxe_populating_popup:
            form, phandle, vu = args
            if vu.item.citype == idaapi.VDI_FUNC or (vu.item.citype == idaapi.VDI_EXPR and vu.item.e.is_expr() and vu.item.e.type.is_funcptr()):
                idaapi.attach_action_to_popup(form, phandle, ACTION_HX_REMOVERETTYPE, None)
        elif event == idaapi.hxe_double_click:
            vu, shift_state = args
            # auto jump to target if clicked item is xxx->func();
            if vu.item.citype == idaapi.VDI_EXPR and vu.item.e.is_expr():
                expr = idaapi.tag_remove(vu.item.e.print1(None))
                if "->" in expr:
                    # find target function
                    name = expr.split("->")[-1]
                    addr = idc.get_name_ea_simple(name)
                    if addr == idaapi.BADADDR:
                        # try class::function
                        e = vu.item.e
                        while e.x:
                            e = e.x
                        addr = idc.get_name_ea_simple("%s::%s" % (str(e.type).split()[0], name))

                    if addr != idaapi.BADADDR:
                        idc.jumpto(addr)
                        return 1
        return 0

class LazyIDA_t(idaapi.plugin_t):
    flags = idaapi.PLUGIN_HIDE
    comment = "LazyIDA"
    help = ""
    wanted_name = "LazyIDA"
    wanted_hotkey = ""

    def init(self):
        self.hexrays_inited = False
        self.registered_actions = []
        self.registered_hx_actions = []

        global ARCH
        global BITS
        ARCH = idaapi.ph_get_id()

        if idaapi.IDA_SDK_VERSION >= 900:
            if idaapi.inf_is_64bit():
                BITS = 64
            elif idaapi.inf_is_32bit_exactly():
                BITS = 32
            elif idaapi.inf_is_16bit():
                BITS = 16
            else:
                raise ValueError
        else:
            info = idaapi.get_inf_structure()
            if info.is_64bit():
                BITS = 64
            elif info.is_32bit():
                BITS = 32
            else:
                BITS = 16

        print("LazyIDA (v1.1.0.0) plugin has been loaded.")

        # Register menu actions
        menu_actions = (
            idaapi.action_desc_t(ACTION_CONVERT[0], "Dump as string", menu_action_handler_t(ACTION_CONVERT[0]), None, None, 80),
            idaapi.action_desc_t(ACTION_CONVERT[1], "Dump as hex string", menu_action_handler_t(ACTION_CONVERT[1]), None, None, 8),
            idaapi.action_desc_t(ACTION_CONVERT[2], "Dump as C/C++ array (BYTE)", menu_action_handler_t(ACTION_CONVERT[2]), None, None, 38),
            idaapi.action_desc_t(ACTION_CONVERT[3], "Dump as C/C++ array (WORD)", menu_action_handler_t(ACTION_CONVERT[3]), None, None, 38),
            idaapi.action_desc_t(ACTION_CONVERT[4], "Dump as C/C++ array (DWORD)", menu_action_handler_t(ACTION_CONVERT[4]), None, None, 38),
            idaapi.action_desc_t(ACTION_CONVERT[5], "Dump as C/C++ array (QWORD)", menu_action_handler_t(ACTION_CONVERT[5]), None, None, 38),
            idaapi.action_desc_t(ACTION_CONVERT[6], "Dump as python list (BYTE)", menu_action_handler_t(ACTION_CONVERT[6]), None, None, 201),
            idaapi.action_desc_t(ACTION_CONVERT[7], "Dump as python list (WORD)", menu_action_handler_t(ACTION_CONVERT[7]), None, None, 201),
            idaapi.action_desc_t(ACTION_CONVERT[8], "Dump as python list (DWORD)", menu_action_handler_t(ACTION_CONVERT[8]), None, None, 201),
            idaapi.action_desc_t(ACTION_CONVERT[9], "Dump as python list (QWORD)", menu_action_handler_t(ACTION_CONVERT[9]), None, None, 201),
            idaapi.action_desc_t(ACTION_XORDATA, "Get xored data", menu_action_handler_t(ACTION_XORDATA), None, None, 9),
        )
        for action in menu_actions:
            idaapi.register_action(action)
            self.registered_actions.append(action.name)

        # Register hotkey actions
        hotkey_actions = (
            idaapi.action_desc_t(ACTION_COPYEA, "Copy EA", hotkey_action_handler_t(ACTION_COPYEA), "w", "Copy current EA", 0),
            idaapi.action_desc_t(ACTION_COPYFO, "Copy FO", hotkey_action_handler_t(ACTION_COPYFO), "Shift-W", "Copy current FO", 0),
            idaapi.action_desc_t(ACTION_GOTOCLIPEA, "Goto clipboard EA", hotkey_action_handler_t(ACTION_GOTOCLIPEA), "Shift-G"),
            idaapi.action_desc_t(ACTION_GOTOCLIPFO, "Goto clipboard FO", hotkey_action_handler_t(ACTION_GOTOCLIPFO), "Ctrl-Shift-G"),
        )
        for action in hotkey_actions:
            idaapi.register_action(action)
            self.registered_actions.append(action.name)

        # Add ui hook
        self.ui_hook = UI_Hook()
        self.ui_hook.hook()

        # Add hexrays ui callback
        if idaapi.init_hexrays_plugin():
            addon = idaapi.addon_info_t()
            addon.id = "tw.l4ys.lazyida"
            addon.name = "LazyIDA"
            addon.producer = "Lays"
            addon.url = "https://github.com/L4ys/LazyIDA"
            addon.version = "1.1.0.0"
            idaapi.register_addon(addon)

            hx_actions = (
                idaapi.action_desc_t(ACTION_HX_REMOVERETTYPE, "Remove return type", hexrays_action_handler_t(ACTION_HX_REMOVERETTYPE), "v"),
                idaapi.action_desc_t(ACTION_HX_COPYEA, "Copy EA", hexrays_action_handler_t(ACTION_HX_COPYEA), "w", "Copy current EA", 0),
                idaapi.action_desc_t(ACTION_HX_COPYFO, "Copy FO", hexrays_action_handler_t(ACTION_HX_COPYFO), "Shift-W", "Copy current FO", 0),
                idaapi.action_desc_t(ACTION_HX_GOTOCLIPEA, "Goto clipboard EA", hexrays_action_handler_t(ACTION_HX_GOTOCLIPEA), "Shift-G"),
                idaapi.action_desc_t(ACTION_HX_GOTOCLIPFO, "Goto clipboard FO", hexrays_action_handler_t(ACTION_HX_GOTOCLIPFO), "Ctrl-Shift-G"),
                idaapi.action_desc_t(ACTION_HX_COPYNAME, "Copy name", hexrays_action_handler_t(ACTION_HX_COPYNAME), "c"),
            )
            for action in hx_actions:
                idaapi.register_action(action)
                self.registered_hx_actions.append(action.name)

            self.hx_hook = HexRays_Hook()
            idaapi.install_hexrays_callback(self.hx_hook.callback)
            self.hexrays_inited = True

        return idaapi.PLUGIN_KEEP

    def run(self, arg):
        pass

    def term(self):
        if hasattr(self, "ui_hook"):
            self.ui_hook.unhook()

        # Unregister actions
        for action in self.registered_actions:
            idaapi.unregister_action(action)

        if self.hexrays_inited:
            # Unregister hexrays actions
            for action in self.registered_hx_actions:
                idaapi.unregister_action(action)
            if self.hx_hook:
                idaapi.remove_hexrays_callback(self.hx_hook.callback)
            idaapi.term_hexrays_plugin()

def PLUGIN_ENTRY():
    return LazyIDA_t()