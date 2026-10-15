package com.rewardassist.wakerelay;
public final class WakePacket {
  public static byte[] create(String mac) {
    if(!mac.matches("(?i)[0-9a-f]{2}([:-][0-9a-f]{2}){5}")) throw new IllegalArgumentException("Enter the PC's six-part MAC address.");
    String[] parts=mac.split("[:-]"); byte[] packet=new byte[102];
    java.util.Arrays.fill(packet,0,6,(byte)255);
    for(int i=6;i<102;i++)packet[i]=(byte)Integer.parseInt(parts[(i-6)%6],16);
    return packet;
  }
}
