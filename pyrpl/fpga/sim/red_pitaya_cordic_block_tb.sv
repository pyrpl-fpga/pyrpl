`timescale 1ns / 1ps

module red_pitaya_cordic_block_tb;
   reg clk = 1'b0;
   reg rstn = 1'b0;
   reg signed [13:0] i = 0;
   reg signed [13:0] q = 0;
   wire signed [13:0] phase;
   integer failures = 0;

   always #4 clk = ~clk;

   red_pitaya_cordic_block dut (
      .clk_i(clk),
      .rstn_i(rstn),
      .i_i(i),
      .q_i(q),
      .phase_o(phase)
   );

   task automatic check_vector;
      input signed [13:0] test_i;
      input signed [13:0] test_q;
      input integer expected;
      input integer tolerance;
      integer cycle;
      integer observed;
      integer error;
      begin
         rstn = 1'b0;
         i = test_i;
         q = test_q;
         repeat (2) @(posedge clk);
         #1;
         rstn = 1'b1;
         for (cycle = 1; cycle <= 11; cycle = cycle + 1) begin
            @(posedge clk);
            #1;
            if ((cycle <= 10) && ($signed(phase) !== 0)) begin
               $display("Unexpected output before cycle 11: cycle=%0d phase=%0d", cycle, $signed(phase));
               failures = failures + 1;
            end
         end
         observed = $signed(phase);
         error = observed - expected;
         if (error < 0)
            error = -error;
         if (error > tolerance) begin
            $display(
               "CORDIC mismatch: I=%0d Q=%0d expected=%0d observed=%0d",
               test_i, test_q, expected, observed
            );
            failures = failures + 1;
         end
      end
   endtask

   initial begin
      // One turn is 4096 output counts.
      check_vector(4096, 0, 0, 4);
      check_vector(0, 4096, 1024, 4);
      check_vector(-4096, 0, 2048, 4);
      check_vector(0, -4096, -1024, 4);
      check_vector(4096, 4096, 512, 4);

      // Exact zero magnitude must hold the last valid phase.
      i = 0;
      q = 0;
      repeat (15) @(posedge clk);
      #1;
      if (($signed(phase) < 508) || ($signed(phase) > 516)) begin
         $display("Zero magnitude did not hold phase: %0d", $signed(phase));
         failures = failures + 1;
      end

      if (failures == 0)
         $display("CORDIC_TEST_PASS");
      else
         $fatal(1, "CORDIC_TEST_FAIL: %0d failure(s)", failures);
      $finish;
   end
endmodule
