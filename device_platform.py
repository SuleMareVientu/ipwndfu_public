class DevicePlatform:
  def __init__(self, cpid, cprv, scep, arch, srtg, rom_base, rom_size, rom_sha1, sram_base, sram_size, dram_base, nonce_length, sep_nonce_length, demotion_reg):
    self.cpid             = cpid
    self.cprv             = cprv
    self.scep             = scep
    self.arch             = arch
    self.srtg             = srtg
    self.rom_base         = rom_base
    self.rom_size         = rom_size
    self.rom_sha1         = rom_sha1
    self.sram_base        = sram_base
    self.sram_size        = sram_size
    self.dram_base        = dram_base
    self.nonce_length     = nonce_length
    self.sep_nonce_length = sep_nonce_length
    self.demotion_reg     = demotion_reg
    if self.cpid == 0x8960:
      self.dfu_image_base      = 0x180380000
      self.dfu_load_base       = 0x83D37B000
      self.recovery_image_base = 0x180380000
      self.recovery_load_base  = 0x800000000

  def name(self):
    if 0x8720 <= self.cpid <= 0x8960:
      return 's5l%xxsi' % self.cpid
    elif self.cpid in [0x7002, 0x8000, 0x8001, 0x8003]:
      return 's%xsi' % self.cpid
    else:
      return 't%xsi' % self.cpid

all_platforms = [
  DevicePlatform(cpid=0x8960, cprv=0x11, scep=0x01, arch='arm64', srtg='iBoot-1704.10',
    rom_base=0x100000000, rom_size=0x80000, rom_sha1='2ae035c46e02ca40ae777f89a6637be694558f0a',
    sram_base=0x180000000, sram_size=0x400000,
    dram_base=0x800000000,
    nonce_length=20, sep_nonce_length=20,
    demotion_reg=0x20E02A000,
  ),
]
