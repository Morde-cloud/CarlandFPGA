module string_probe;
    task automatic say(input string message);
        $display(message);
    endtask
    initial begin
        say(APWM_HELLO);
        $display(APWM_PASS);
        $finish(0);
    end
endmodule
