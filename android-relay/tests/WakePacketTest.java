package com.rewardassist.wakerelay;
import java.util.Arrays;
public final class WakePacketTest {
  public static void main(String[] args) {
    byte[] packet=WakePacket.create("34:5A:60:BA:70:7C");
    if(packet.length!=102)throw new AssertionError("Packet length");
    for(int i=0;i<6;i++)if(packet[i]!=(byte)255)throw new AssertionError("Magic prefix");
    byte[] mac={(byte)0x34,(byte)0x5A,(byte)0x60,(byte)0xBA,(byte)0x70,(byte)0x7C};
    for(int i=0;i<16;i++)if(!Arrays.equals(mac,Arrays.copyOfRange(packet,6+i*6,12+i*6)))throw new AssertionError("MAC repetition");
    for(String invalid:new String[]{"", "34:5A:60:BA:70", "GG:5A:60:BA:70:7C", "34:5A:60:BA:70:7C:00"}) {
      try { WakePacket.create(invalid); throw new AssertionError("Accepted malformed MAC"); } catch(IllegalArgumentException expected) {}
    }
    System.out.println("Wake packet tests passed");
  }
}
