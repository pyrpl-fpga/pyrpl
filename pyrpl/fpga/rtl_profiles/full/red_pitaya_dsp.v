/*
###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
*/
/***********************************************************
DSP Module - "full" profile (Zynq 7020 only)

All optional DSP features in one image:
 - 3 PIDs with four input-filter stages and a band-limited derivative
 - pipelined 32-bit / 14-stage IIR in slot 4
 - 3 IQs with VCO control; IQ0/IQ1 with integrated CORDICs
 - standalone two-input CORDIC
 - two-input arithmetic module

Routing codes and register slots
--------------------------------
Every module keeps the routing code and register address it has in the other
profiles. The 16 historical routing codes (0..15, 15 = off) are all in use, so
the selectors are widened to 5 bits and the two additional modules get new
codes:

   code/slot  module        register base
   0..2       pid0..pid2    0x40300000 + slot*0x10000
   3          trig
   4          iir
   5..7       iq0..iq2
   8, 9       asg0/asg1 (scope0/scope1 inputs)
   10, 11     in1/in2 (pwm0/pwm1 inputs)
   12, 13     out1/out2
   14         iq2_2
   15         off
   16         cordic        0x40500000
   17         arithmetic    0x40510000

Slots 16..31 live in system-bus region 5 (0x40500000..0x405FFFFF), which the
top level forwards to this module when DSP_HIGH_SLOTS = 1. The slot number is
{region is 5, sys_addr[19:16]}; region 3 has sys_addr[21] = 1 and region 5 has
sys_addr[21] = 0.

As in the other profiles, offsets 0x00..0x1C of each slot are routing
registers handled here:
   0x00 input_select   0x04 output_select   0x08 DAC saturation
   0x0C sync           0x10 current output_signal
   0x14 second input: cordic Q select / arithmetic input B / IQ VCO input
   0x18 cordic ABI signature   0x1C cordic input pair
*************************************************************/


module red_pitaya_dsp #(
	parameter MODULES = 8,  // unused; kept for a uniform top-level interface
	parameter PID_DERIVATIVE = 1,
	parameter PID_FILTERSTAGES = 4,
	parameter PID_DERIVATIVE_FILTER_SHIFT = 4,
	parameter IQ_VCO = 1,
	parameter ARITHMETIC = 1  // unused; the arithmetic module is always present
)
(
   // signals
   input                 clk_i           ,  //!< processing clock
   input                 rstn_i          ,  //!< processing reset - active low
   input      [ 14-1: 0] dat_a_i         ,  //!< input data CHA
   input      [ 14-1: 0] dat_b_i         ,  //!< input data CHB
   output     [ 14-1: 0] dat_a_o         ,  //!< output data CHA
   output     [ 14-1: 0] dat_b_o         ,  //!< output data CHB

   output     [ 14-1: 0] scope1_o,
   output     [ 14-1: 0] scope2_o,
   input      [ 14-1: 0] asg1_i,
   input      [ 14-1: 0] asg2_i,
   input      [ 14-1: 0] asg1phase_i,
   input      [ 16-1: 0] iq_trigger_i,
   input      [ 16-1: 0] pid_enable_i,

   // pwm outputs
   output     [ 14-1: 0] pwm0,
   output     [ 14-1: 0] pwm1,
   output     [ 14-1: 0] pwm2,
   output     [ 14-1: 0] pwm3,

   // trigger outputs for the scope
   output                trig_o,   // output from trigger dsp module

   // system bus
   input      [ 32-1: 0] sys_addr        ,  //!< bus address
   input      [ 32-1: 0] sys_wdata       ,  //!< bus write data
   input      [  4-1: 0] sys_sel         ,  //!< bus write byte select
   input                 sys_wen         ,  //!< bus write enable
   input                 sys_ren         ,  //!< bus read enable
   output reg [ 32-1: 0] sys_rdata   ,  //!< bus read data
   output reg            sys_err         ,  //!< bus error indicator
   output reg            sys_ack            //!< bus acknowledge signal
);

localparam LOG_MODULES = 5;          // width of routing codes
localparam CODES       = 2**LOG_MODULES;
localparam SLOTS       = 18;         // register slots 0..17

//Module numbers (routing code == register slot == sync bit)
localparam PID0   = 'd0;
localparam PID1   = 'd1;
localparam PID2   = 'd2;
localparam TRIG   = 'd3;
localparam IIR    = 'd4;
localparam IQ0    = 'd5;
localparam IQ1    = 'd6;
localparam IQ2    = 'd7;
localparam ASG1   = 'd8;   // scope and asg share a number:
localparam ASG2   = 'd9;   // one only has outputs, the other only inputs
localparam SCOPE1 = 'd8;
localparam SCOPE2 = 'd9;
localparam ADC1   = 'd10;
localparam ADC2   = 'd11;
localparam PWM0   = 'd10;
localparam PWM1   = 'd11;
localparam DAC1   = 'd12;
localparam DAC2   = 'd13;
localparam IQ2_2  = 'd14;
localparam NONE   = 'd15;  // historical "off" code, kept for compatibility
localparam CORDIC = 'd16;
localparam ARITH  = 'd17;

//output states
localparam BOTH = 2'b11;
localparam OUT1 = 2'b01;
localparam OUT2 = 2'b10;
localparam OFF  = 2'b00;

// register slot addressed by the current bus access
wire [LOG_MODULES-1:0] slot = {~sys_addr[21], sys_addr[19:16]};

// the selected input signal of each slot
wire [14-1:0] input_signal [SLOTS-1:0];
// the selected input signal NUMBER of each slot
reg [LOG_MODULES-1:0] input_select [SLOTS-1:0];

// the output of each routing code
wire [14-1:0] output_signal [CODES-1:0];

// the output of each slot that is added to the chosen DAC
wire [14-1:0] output_direct [SLOTS-1:0];
// the channel that the slot's output_direct is added to (bit0: DAC1, bit 1: DAC2)
reg [2-1:0] output_select [SLOTS-1:0];

// syncronization register to trigger simultaneous action of different dsp modules
reg [SLOTS-1:0] sync;

// IQ quadratures remain available locally for the CORDICs.
wire signed [14-1:0] iq_quadrature_i [2:0];
wire signed [14-1:0] iq_quadrature_q [2:0];

// Standalone CORDIC: input_select gives I, a second selector gives Q, or a
// local IQ quadrature pair is used directly.
reg [LOG_MODULES-1:0] cordic_input_q_select;
reg [1:0] cordic_input_pair;
wire signed [14-1:0] cordic_independent_q =
   (cordic_input_q_select == NONE) ? 14'sd0 :
   output_signal[cordic_input_q_select];
wire signed [14-1:0] cordic_input_i =
   (cordic_input_pair == 2'd1) ? iq_quadrature_i[0] :
   (cordic_input_pair == 2'd2) ? iq_quadrature_i[1] :
   (cordic_input_pair == 2'd3) ? iq_quadrature_i[2] :
   input_signal[CORDIC];
wire signed [14-1:0] cordic_input_q =
   (cordic_input_pair == 2'd1) ? iq_quadrature_q[0] :
   (cordic_input_pair == 2'd2) ? iq_quadrature_q[1] :
   (cordic_input_pair == 2'd3) ? iq_quadrature_q[2] :
   cordic_independent_q;

// Arithmetic: input_select gives input A, a second selector gives input B.
reg [LOG_MODULES-1:0] arithmetic_input_b_select;
wire signed [14-1:0] arithmetic_input_b =
   (arithmetic_input_b_select == NONE) ? 14'sd0 :
   output_signal[arithmetic_input_b_select];

// Each IQ can independently use any DSP output as its VCO control signal.
reg [LOG_MODULES-1:0] vco_select [IQ2:IQ0];

// bus read data of individual slots
wire [ 32-1: 0] module_rdata [SLOTS-1:0];
wire            module_ack   [SLOTS-1:0];

//connect scope
assign scope1_o = input_signal[SCOPE1];
assign scope2_o = input_signal[SCOPE2];

//connect asg output
assign output_signal[ASG1] = asg1_i;
assign output_signal[ASG2] = asg2_i;
assign output_direct[ASG1] = asg1_i;
assign output_direct[ASG2] = asg2_i;

//connect dac/adc to internal signals
assign output_signal[ADC1] = dat_a_i;
assign output_signal[ADC2] = dat_b_i;
assign output_signal[DAC1] = dat_a_o;
assign output_signal[DAC2] = dat_b_o;

// unused routing codes and slots
assign output_signal[NONE] = 14'd0;
genvar j;
generate for (j = ARITH+1; j < CODES; j = j+1) begin : unused_codes
   assign output_signal[j] = 14'd0;
end endgenerate
generate for (j = ADC1; j < CORDIC; j = j+1) begin : unused_slots
   // slots 10..15 hold routing registers only (pwm inputs, sampler readout)
   assign output_direct[j] = 14'd0;
   assign module_ack[j]    = sys_wen | sys_ren;
   assign module_rdata[j]  = 32'd0;
end endgenerate
generate for (j = SCOPE1; j <= SCOPE2; j = j+1) begin : asg_slots
   assign module_ack[j]    = sys_wen | sys_ren;
   assign module_rdata[j]  = 32'd0;
end endgenerate

//connect only two pwm to internal signals (should be enough)
assign pwm0 = (input_select[PWM0] == NONE) ? 14'h0 : output_signal[input_select[PWM0]];
assign pwm1 = (input_select[PWM1] == NONE) ? 14'h0 : output_signal[input_select[PWM1]];
assign pwm2 = 14'b0;
assign pwm3 = 14'b0;

wire dac_a_saturated; //high when dac_a is saturated
wire dac_b_saturated; //high when dac_b is saturated

integer i;

//select inputs
generate for (j = 0; j < SLOTS; j = j+1) begin : input_mux
   assign input_signal[j] = (input_select[j]==NONE) ? 14'b0 : output_signal[input_select[j]];
end endgenerate

//sum together the direct outputs
//
// Same pipeline as the other profiles: one stage of pairs, three tree stages
// for 16 channels, one output register. The twelve summed slots (0..9, 16, 17)
// are packed into the 16 channels; the remaining channels are zero.
localparam CHANNELS = 16;
localparam SUMBITS = 14 + 4;  // 16 summands
wire [14-1:0] channel_direct [CHANNELS-1:0];
wire [2-1:0]  channel_select [CHANNELS-1:0];
generate for (j = 0; j < 10; j = j+1) begin : direct_channels
   assign channel_direct[j] = output_direct[j];
   assign channel_select[j] = output_select[j];
end endgenerate
assign channel_direct[10] = output_direct[CORDIC];
assign channel_select[10] = output_select[CORDIC];
assign channel_direct[11] = output_direct[ARITH];
assign channel_select[11] = output_select[ARITH];
generate for (j = 12; j < CHANNELS; j = j+1) begin : empty_channels
   assign channel_direct[j] = 14'd0;
   assign channel_select[j] = OFF;
end endgenerate

reg  signed [SUMBITS-1: 0] presum1 [CHANNELS-1-1:0];
reg  signed [SUMBITS-1: 0] presum2 [CHANNELS-1-1:0];
reg  signed [SUMBITS-1: 0] sum1;
reg  signed [SUMBITS-1: 0] sum2;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
     for (i=0;i<CHANNELS-1;i=i+1) begin
        presum1[i] <= {SUMBITS{1'b0}};
        presum2[i] <= {SUMBITS{1'b0}};
     end
     sum1 <= {SUMBITS{1'b0}};
     sum2 <= {SUMBITS{1'b0}};
   end
   else begin
     //first sum pairs if they are set to be summed
     for (i=0;i<CHANNELS/2;i=i+1) begin
        presum1[i] <= ({SUMBITS{(|(channel_select[2*i]&OUT1))}} & {{4{channel_direct[2*i][14-1]}},channel_direct[2*i]}) + ({SUMBITS{(|(channel_select[2*i+1]&OUT1))}} & {{4{channel_direct[2*i+1][14-1]}},channel_direct[2*i+1]});
        presum2[i] <= ({SUMBITS{(|(channel_select[2*i]&OUT2))}} & {{4{channel_direct[2*i][14-1]}},channel_direct[2*i]}) + ({SUMBITS{(|(channel_select[2*i+1]&OUT2))}} & {{4{channel_direct[2*i+1][14-1]}},channel_direct[2*i+1]});
     end
     //then sum the sums of pairs to go up the tree
     for (i=0;i<CHANNELS/2-1;i=i+1) begin
        presum1[CHANNELS/2+i] <= presum1[2*i]+presum1[2*i+1];
        presum2[CHANNELS/2+i] <= presum2[2*i]+presum2[2*i+1];
     end
     sum1 <= presum1[CHANNELS-1-1];
     sum2 <= presum2[CHANNELS-1-1];
   end
end

//saturation of outputs
red_pitaya_saturate #(
    .BITS_IN (SUMBITS),
    .SHIFT(0),
    .BITS_OUT(14)
    ) dac_saturate [1:0] (
   .input_i({sum2,sum1}),
   .output_o({dat_b_o,dat_a_o}),
   .overflow ({dat_b_saturated,dac_a_saturated})
   );

//  System bus connection
always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      for (i=0;i<SLOTS;i=i+1) begin
         input_select [i] <= ADC1;
         output_select[i] <= OFF;
      end
      input_select [SCOPE2] <= ADC2;
      input_select [PWM0] <= NONE;
      input_select [PWM1] <= NONE;

      cordic_input_q_select <= ADC2;
      cordic_input_pair <= 2'd0;
      arithmetic_input_b_select <= ADC2;
      for (i=IQ0;i<=IQ2;i=i+1)
         vco_select[i] <= NONE;

      sync <= {SLOTS{1'b1}} ;  // all modules on by default
   end
   else begin
      if (sys_wen && (slot < SLOTS)) begin
         if (sys_addr[16-1:0]==16'h00)     input_select[slot] <= sys_wdata[ LOG_MODULES-1:0];
         if (sys_addr[16-1:0]==16'h04)    output_select[slot] <= sys_wdata[ 2-1:0];
         if (sys_addr[16-1:0]==16'h0C)                  sync <= sys_wdata[SLOTS-1:0];
         if (sys_addr[16-1:0]==16'h14) begin
            if (slot == CORDIC)
               cordic_input_q_select <= sys_wdata[LOG_MODULES-1:0];
            else if (slot == ARITH)
               arithmetic_input_b_select <= sys_wdata[LOG_MODULES-1:0];
            else if ((slot >= IQ0) && (slot <= IQ2))
               vco_select[slot] <= sys_wdata[LOG_MODULES-1:0];
         end
         if ((sys_addr[16-1:0]==16'h1C) && (slot == CORDIC))
            cordic_input_pair <= sys_wdata[1:0];
      end
   end
end

wire sys_en;
assign sys_en = sys_wen | sys_ren;
always @(posedge clk_i)
if (rstn_i == 1'b0) begin
   sys_err <= 1'b0 ;
   sys_ack <= 1'b0 ;
end else if (slot >= SLOTS) begin
   // unmapped slots in region 5: acknowledge with zero data
   sys_err   <= 1'b0;
   sys_ack   <= sys_en;
   sys_rdata <= 32'd0;
end else begin
   sys_err <= 1'b0 ;
   casez (sys_addr[16-1:0])
      16'h00 : begin sys_ack <= sys_en;          sys_rdata <= {{32- LOG_MODULES{1'b0}},input_select[slot]}; end
      16'h04 : begin sys_ack <= sys_en;          sys_rdata <= {{32- 2{1'b0}},output_select[slot]}; end
      16'h08 : begin sys_ack <= sys_en;          sys_rdata <= {{32- 2{1'b0}},dat_b_saturated,dac_a_saturated}; end
      16'h0C : begin sys_ack <= sys_en;          sys_rdata <= {{32-SLOTS{1'b0}},sync} ; end
      16'h10 : begin sys_ack <= sys_en;          sys_rdata <= {{32- 14{1'b0}},output_signal[slot]} ; end
      16'h14 : begin
         if (slot == CORDIC) begin
            sys_ack <= sys_en;
            sys_rdata <= {{32-LOG_MODULES{1'b0}}, cordic_input_q_select};
         end else if (slot == ARITH) begin
            sys_ack <= sys_en;
            sys_rdata <= {{32-LOG_MODULES{1'b0}}, arithmetic_input_b_select};
         end else if ((slot >= IQ0) && (slot <= IQ2)) begin
            sys_ack <= sys_en;
            sys_rdata <= {{32-LOG_MODULES{1'b0}}, vco_select[slot]};
         end else begin
            sys_ack <= module_ack[slot];
            sys_rdata <= module_rdata[slot];
         end
      end
      16'h18 : begin
         if (slot == CORDIC) begin
            sys_ack <= sys_en;
            sys_rdata <= 32'h434F5202;
         end else begin
            sys_ack <= module_ack[slot];
            sys_rdata <= module_rdata[slot];
         end
      end
      16'h1C : begin
         if (slot == CORDIC) begin
            sys_ack <= sys_en;
            sys_rdata <= {30'd0, cordic_input_pair};
         end else begin
            sys_ack <= module_ack[slot];
            sys_rdata <= module_rdata[slot];
         end
      end
     default : begin sys_ack <= module_ack[slot];    sys_rdata <=  module_rdata[slot]  ; end
   endcase
end


/**********************************************
 MODULE DEFINITIONS
 *********************************************/

//PID

wire [14-1:0] diff_input_signal [3-1:0];
wire [14-1:0] diff_output_signal [3-1:0];
assign diff_input_signal[0] = diff_output_signal[1]; // difference input of PID0 is PID1
assign diff_input_signal[1] = diff_output_signal[0]; // difference input of PID1 is PID0
assign diff_input_signal[2] = {14{1'b0}};      // difference input of PID2 is zero

generate for (j = 0; j < 3; j = j+1) begin : pid
   red_pitaya_pid_block #(
     .DERIVATIVE              ( PID_DERIVATIVE              ),
     .INPUT_REGISTER          ( PID_DERIVATIVE && (PID_FILTERSTAGES > 0) ),
     .FILTERSTAGES            ( PID_FILTERSTAGES            ),
     .DERIVATIVE_FILTER_SHIFT ( PID_DERIVATIVE_FILTER_SHIFT )
   ) i_pid (
     .clk_i        (  clk_i          ),
     .rstn_i       (  rstn_i         ),
     .sync_i       (  sync[j]        ),
     .external_enable_i ( pid_enable_i ),
     .dat_i        (  input_signal [j] ),
     .dat_o        (  output_direct[j]),
     .diff_dat_i   (  diff_input_signal[j] ),
     .diff_dat_o   (  diff_output_signal[j] ),

     .addr ( sys_addr[16-1:0] ),
     .wen  ( sys_wen & (slot==j) ),
     .ren  ( sys_ren & (slot==j) ),
     .ack  ( module_ack[j] ),
     .rdata (module_rdata[j]),
     .wdata (sys_wdata)
   );
   assign output_signal[j] = output_direct[j];
end
endgenerate

//TRIG
wire trig_signal;
red_pitaya_trigger_block i_trigger (
  .clk_i        (  clk_i          ),
  .rstn_i       (  rstn_i         ),
  .dat_i        (  input_signal [TRIG] ),
  .dat_o        (  output_direct[TRIG]),
  .signal_o     (  output_signal[TRIG]),
  .phase1_i     (  asg1phase_i ),
  .trig_o       (  trig_signal ),

  .addr ( sys_addr[16-1:0] ),
  .wen  ( sys_wen & (slot==TRIG) ),
  .ren  ( sys_ren & (slot==TRIG) ),
  .ack  ( module_ack[TRIG] ),
  .rdata (module_rdata[TRIG]),
  .wdata (sys_wdata)
);
assign trig_o = trig_signal;

//IIR module: pipelined 32-bit / 14-stage (as in the iir32 profile)
red_pitaya_iir_block #(
     .IIRBITS(32),
     .IIRSHIFT(29),
     .IIRSTAGES(14),
     .IIRSIGNALBITS(32)
  ) iir (
     .clk_i        (  clk_i          ),
     .rstn_i       (  rstn_i         ),
     .dat_i        (  input_signal [IIR] ),
     .dat_o        (  output_direct[IIR]),

     .addr ( sys_addr[16-1:0] ),
     .wen  ( sys_wen & (slot==IIR) ),
     .ren  ( sys_ren & (slot==IIR) ),
     .ack  ( module_ack[IIR] ),
     .rdata (module_rdata[IIR]),
     .wdata (sys_wdata)
  );
assign output_signal[IIR] = output_direct[IIR];

// Standalone vectoring CORDIC
wire signed [14-1:0] cordic_phase;
red_pitaya_cordic_block i_cordic (
   .clk_i   (clk_i),
   .rstn_i  (rstn_i),
   .i_i     (cordic_input_i),
   .q_i     (cordic_input_q),
   .phase_o (cordic_phase)
);
assign output_direct[CORDIC] = cordic_phase;
assign output_signal[CORDIC] = cordic_phase;
assign module_ack[CORDIC] = sys_en;
assign module_rdata[CORDIC] = 32'd0;

// Two-input arithmetic module
red_pitaya_arithmetic_block i_arithmetic (
   .clk_i  (clk_i),
   .rstn_i (rstn_i),
   .dat_a_i(input_signal[ARITH]),
   .dat_b_i(arithmetic_input_b),
   .dat_o  (output_direct[ARITH]),
   .addr   (sys_addr[15:0]),
   .wen    (sys_wen & (slot == ARITH)),
   .ren    (sys_ren & (slot == ARITH)),
   .ack    (module_ack[ARITH]),
   .rdata  (module_rdata[ARITH]),
   .wdata  (sys_wdata)
);
assign output_signal[ARITH] = output_direct[ARITH];

//IQ modules with integrated CORDICs and VCO inputs
generate for (j = IQ0; j < IQ2; j = j+1) begin : iq_cordic
    red_pitaya_iq_block #(
      .VCO_ENABLED       ( IQ_VCO ),
      .CORDIC_ENABLED    ( 1      ),
      .MODULATOR_PIPELINE( 1      )
    ) iq (
      .clk_i        (  clk_i          ),
      .rstn_i       (  rstn_i         ),
      .sync_i       (  sync[j]        ),
      .external_trigger_i ( iq_trigger_i ),
      .vco_i        ( (vco_select[j] == NONE) ? 14'sd0 :
                      output_signal[vco_select[j]] ),
      .dat_i        (  input_signal [j] ),
      .dat_o        (  output_direct[j]),
      .signal_o     (  output_signal[j]),
      .quadrature1_o(  iq_quadrature_i[j-IQ0]),
      .quadrature2_o(  iq_quadrature_q[j-IQ0]),

      .addr ( sys_addr[16-1:0] ),
      .wen  ( sys_wen & (slot==j) ),
      .ren  ( sys_ren & (slot==j) ),
      .ack  ( module_ack[j] ),
      .rdata (module_rdata[j]),
      .wdata (sys_wdata)
    );
end endgenerate

// IQ with two outputs (network/spectrum analyzer), VCO input
red_pitaya_iq_block #(
  .QUADRATUREFILTERSTAGES ( 4      ),
  .VCO_ENABLED            ( IQ_VCO ),
  .MODULATOR_PIPELINE     ( 1      )
) iq_2_outputs (
  .clk_i        (  clk_i          ),
  .rstn_i       (  rstn_i         ),
  .sync_i       (  sync[IQ2]      ),
  .external_trigger_i ( iq_trigger_i ),
  .vco_i        ( (vco_select[IQ2] == NONE) ? 14'sd0 :
                  output_signal[vco_select[IQ2]] ),
  .dat_i        (  input_signal [IQ2] ),
  .dat_o        (  output_direct[IQ2]),
  .signal_o     (  output_signal[IQ2]),
  .signal2_o    (  output_signal[IQ2_2]),
  .quadrature1_o(  iq_quadrature_i[IQ2-IQ0]),
  .quadrature2_o(  iq_quadrature_q[IQ2-IQ0]),

  .addr ( sys_addr[16-1:0] ),
  .wen  ( sys_wen & (slot==IQ2) ),
  .ren  ( sys_ren & (slot==IQ2) ),
  .ack  ( module_ack[IQ2] ),
  .rdata (module_rdata[IQ2]),
  .wdata (sys_wdata)
);

endmodule
