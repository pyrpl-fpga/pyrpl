`timescale 1ns / 1ps

/*
 * Pipelined vectoring CORDIC.
 *
 * The output is an unwrapped phase in turns. PHASE_WIDTH bits encode the
 * fractional turn and TURN_WIDTH signed bits count complete turns. With the
 * default widths, one output LSB is 1/4096 turn and the representable interval
 * spans four turns.
 */
module red_pitaya_cordic_block #(
   parameter SIGNAL_BITS = 14,
   parameter INPUT_WIDTH = 14,
   parameter WORKING_WIDTH = 16,
   parameter PHASE_WIDTH = 12,
   parameter TURN_WIDTH = 2,
   parameter STAGES = 9
) (
   input  wire                          clk_i,
   input  wire                          rstn_i,
   input  wire signed [INPUT_WIDTH-1:0] i_i,
   input  wire signed [INPUT_WIDTH-1:0] q_i,
   output wire signed [SIGNAL_BITS-1:0] phase_o
);

localparam EXTRA_PRECISION = WORKING_WIDTH - INPUT_WIDTH - 2;

wire signed [WORKING_WIDTH-1:0] extended_i = {
   {2{i_i[INPUT_WIDTH-1]}}, i_i, {EXTRA_PRECISION{1'b0}}
};
wire signed [WORKING_WIDTH-1:0] extended_q = {
   {2{q_i[INPUT_WIDTH-1]}}, q_i, {EXTRA_PRECISION{1'b0}}
};

reg signed [WORKING_WIDTH-1:0] i_value [0:STAGES];
reg signed [WORKING_WIDTH-1:0] q_value [0:STAGES];
reg        [PHASE_WIDTH-1:0]   phase   [0:STAGES];
reg                              valid   [0:STAGES];

reg signed [TURN_WIDTH-1:0] turns;
reg        [PHASE_WIDTH-1:0] phase_fraction;
reg        [1:0]             last_quadrant;
reg                          phase_valid;

assign phase_o = {turns, phase_fraction};

// Rotate the input into [-45, +45] degrees. The phase constants retain the
// inverse rotation, so the pipeline computes atan2(Q, I), not an IQ-specific
// phase with an implicit half-turn offset.
always @(posedge clk_i) begin
   if (!rstn_i) begin
      i_value[0] <= 0;
      q_value[0] <= 0;
      phase[0] <= 0;
      valid[0] <= 1'b0;
   end else begin
      valid[0] <= (|i_i) || (|q_i);
      case ({extended_i[WORKING_WIDTH-1], extended_q[WORKING_WIDTH-1]})
         2'b00: begin
            i_value[0] <= extended_i + extended_q;
            q_value[0] <= -extended_i + extended_q;
            phase[0] <= 12'h200; // +45 degrees
         end
         2'b01: begin
            i_value[0] <= extended_i - extended_q;
            q_value[0] <= extended_i + extended_q;
            phase[0] <= 12'hE00; // -45 degrees
         end
         2'b10: begin
            i_value[0] <= -extended_i + extended_q;
            q_value[0] <= -extended_i - extended_q;
            phase[0] <= 12'h600; // +135 degrees
         end
         default: begin
            i_value[0] <= -extended_i - extended_q;
            q_value[0] <= extended_i - extended_q;
            phase[0] <= 12'hA00; // -135 degrees
         end
      endcase
   end
end

wire [PHASE_WIDTH-1:0] cordic_angle [0:STAGES-1];
assign cordic_angle[0] = 12'h12E; // atan(2^-1)
assign cordic_angle[1] = 12'h09F; // atan(2^-2)
assign cordic_angle[2] = 12'h051; // atan(2^-3)
assign cordic_angle[3] = 12'h028; // atan(2^-4)
assign cordic_angle[4] = 12'h014; // atan(2^-5)
assign cordic_angle[5] = 12'h00A; // atan(2^-6)
assign cordic_angle[6] = 12'h005; // atan(2^-7)
assign cordic_angle[7] = 12'h002; // atan(2^-8)
assign cordic_angle[8] = 12'h001; // atan(2^-9)

genvar stage;
generate for (stage = 0; stage < STAGES; stage = stage + 1) begin : cordic_stage
   always @(posedge clk_i) begin
      if (!rstn_i) begin
         i_value[stage+1] <= 0;
         q_value[stage+1] <= 0;
         phase[stage+1] <= 0;
         valid[stage+1] <= 1'b0;
      end else begin
         valid[stage+1] <= valid[stage];
         if (q_value[stage][WORKING_WIDTH-1]) begin
            i_value[stage+1] <=
               i_value[stage] - (q_value[stage] >>> (stage + 1));
            q_value[stage+1] <=
               q_value[stage] + (i_value[stage] >>> (stage + 1));
            phase[stage+1] <= phase[stage] - cordic_angle[stage];
         end else begin
            i_value[stage+1] <=
               i_value[stage] + (q_value[stage] >>> (stage + 1));
            q_value[stage+1] <=
               q_value[stage] - (i_value[stage] >>> (stage + 1));
            phase[stage+1] <= phase[stage] + cordic_angle[stage];
         end
      end
   end
end endgenerate

// Convert the wrapped fractional phase into a continuous phase. Exact zero
// magnitude is invalid and holds the last output instead of producing an
// arbitrary angle.
always @(posedge clk_i) begin
   if (!rstn_i) begin
      turns <= 0;
      phase_fraction <= 0;
      last_quadrant <= 0;
      phase_valid <= 1'b0;
   end else if (valid[STAGES]) begin
      phase_fraction <= phase[STAGES];
      last_quadrant <= phase[STAGES][PHASE_WIDTH-1:PHASE_WIDTH-2];
      if (!phase_valid) begin
         // Start in the canonical [-0.5, +0.5) turn interval.
         turns <= phase[STAGES][PHASE_WIDTH-1] ? {TURN_WIDTH{1'b1}} : 0;
         phase_valid <= 1'b1;
      end else begin
         case (last_quadrant)
            2'b00: begin
               if ((phase[STAGES][PHASE_WIDTH-1:PHASE_WIDTH-2] == 2'b11) &&
                   (turns != {1'b1, {(TURN_WIDTH-1){1'b0}}}))
                  turns <= turns - 1'b1;
            end
            2'b11: begin
               if ((phase[STAGES][PHASE_WIDTH-1:PHASE_WIDTH-2] == 2'b00) &&
                   (turns != {1'b0, {(TURN_WIDTH-1){1'b1}}}))
                  turns <= turns + 1'b1;
            end
            default: turns <= turns;
         endcase
      end
   end
end

endmodule
