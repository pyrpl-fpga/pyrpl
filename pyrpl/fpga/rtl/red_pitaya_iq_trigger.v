`timescale 1ns / 1ps

/*
 * Edge-trigger controller for an IQ local oscillator.
 *
 * The expansion inputs are synchronized in red_pitaya_dsp before reaching
 * this block.  Immediate mode preserves the historical sync_i behavior.
 * External mode waits for one rising edge and then runs continuously until
 * the IQ is explicitly rearmed or the global IQ synchronization is asserted.
 */
module red_pitaya_iq_trigger (
   input  clk_i,
   input  rstn_i,
   input  sync_i,
   input  external_i,
   input  external_mode_i,
   input  rearm_i,
   output on_o
);

reg external_d;
reg external_triggered;

assign on_o = external_mode_i ? (sync_i && external_triggered) : sync_i;

always @(posedge clk_i) begin
   if (!rstn_i) begin
      external_d <= 1'b0;
      external_triggered <= 1'b0;
   end else if (!external_mode_i) begin
      external_d <= 1'b0;
      external_triggered <= 1'b0;
   end else if (rearm_i || !sync_i) begin
      external_d <= 1'b0;
      external_triggered <= 1'b0;
   end else begin
      external_d <= external_i;
      if (external_i && !external_d)
         external_triggered <= 1'b1;
   end
end

endmodule
