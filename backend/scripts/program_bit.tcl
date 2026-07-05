set bitfile [lindex $argv 0]
set hw_target [lindex $argv 1]
set device_name [lindex $argv 2]

if {$bitfile eq ""} {
    puts "ERROR: bit file path is required"
    exit 2
}

if {![file exists $bitfile]} {
    puts "ERROR: bit file does not exist: $bitfile"
    exit 3
} 

open_hw_manager
connect_hw_server

set all_targets [get_hw_targets]
if {[llength $all_targets] == 0} {
    puts "ERROR: no hardware targets found"
    close_hw_manager
    exit 4
}

if {$hw_target ne ""} {
    set matched_targets [get_hw_targets $hw_target]
    if {[llength $matched_targets] == 0} {
        puts "ERROR: hardware target not found: $hw_target"
        close_hw_manager
        exit 5
    }
    current_hw_target [lindex $matched_targets 0]
} else {
    current_hw_target [lindex $all_targets 0]
}

open_hw_target

set all_devices [get_hw_devices]
if {[llength $all_devices] == 0} {
    puts "ERROR: no hardware devices found"
    close_hw_manager
    exit 6
}

if {$device_name ne ""} {
    set matched_devices [get_hw_devices $device_name]
    if {[llength $matched_devices] == 0} {
        puts "ERROR: hardware device not found: $device_name"
        close_hw_manager
        exit 7
    }
    set device [lindex $matched_devices 0]
} else {
    set device [lindex $all_devices 0]
}

current_hw_device $device
refresh_hw_device $device
set_property PROGRAM.FILE $bitfile $device
program_hw_devices $device
refresh_hw_device $device

puts "INFO: programmed bit file $bitfile to $device"

close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
