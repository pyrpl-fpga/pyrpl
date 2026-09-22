`timescale 1ns / 1ps

module red_pitaya_iq_trigger_tb;

reg clk = 1'b0;
reg rstn = 1'b0;
reg sync = 1'b0;
reg external_trigger = 1'b0;
reg external_mode = 1'b0;
reg rearm = 1'b0;
wire on;

always #4 clk = ~clk;

red_pitaya_iq_trigger dut (
   .clk_i(clk),
   .rstn_i(rstn),
   .sync_i(sync),
   .external_i(external_trigger),
   .external_mode_i(external_mode),
   .rearm_i(rearm),
   .on_o(on)
);

task check;
   input expected;
   input [8*64-1:0] description;
   begin
      #1;
      if (on !== expected) begin
         $display("IQ_TRIGGER_TEST_FAIL: %s (expected %b, got %b)",
                  description, expected, on);
         $finish;
      end
   end
endtask

task tick;
   begin
      @(posedge clk);
      #1;
   end
endtask

initial begin
   repeat (2) tick();
   rstn = 1'b1;
   sync = 1'b1;
   tick();
   check(1'b1, "immediate mode follows sync");

   external_mode = 1'b1;
   rearm = 1'b1;
   tick();
   rearm = 1'b0;
   check(1'b0, "external mode waits while armed");

   external_trigger = 1'b1;
   tick();
   check(1'b1, "rising edge starts oscillator");
   external_trigger = 1'b0;
   tick();
   check(1'b1, "falling edge does not stop oscillator");

   rearm = 1'b1;
   tick();
   rearm = 1'b0;
   check(1'b0, "register write rearms trigger");
   repeat (2) tick();
   check(1'b0, "low input remains armed");

   external_trigger = 1'b1;
   tick();
   check(1'b1, "second rising edge retriggers");
   sync = 1'b0;
   tick();
   check(1'b0, "global synchronization stops and rearms");
   external_trigger = 1'b0;
   sync = 1'b1;
   tick();
   check(1'b0, "external mode waits after global rearm");

   external_mode = 1'b0;
   tick();
   check(1'b1, "return to immediate mode");

   $display("IQ_TRIGGER_TEST_PASS");
   $finish;
end

endmodule
