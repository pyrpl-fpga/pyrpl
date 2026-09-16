# Frozen legacy RTL overrides

These files preserve the original unpipelined FPGA implementation used by the
`legacy` profile. They are compatibility sources for reproducing the old
bitstream and are not the active implementation.

New development belongs in `../rtl` or a narrowly scoped override under
`../rtl_profiles`. Do not apply ordinary maintenance changes here unless the
legacy bitstream itself must be rebuilt with that change.
