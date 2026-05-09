import { readSeedFile, type Coupon } from '../db';

export async function loadSeedCoupons(): Promise<Coupon[]> {
  return readSeedFile<Coupon[]>('coupons.json');
}

export async function searchCouponsByPoi(poiId: string): Promise<Coupon[]> {
  return (await loadSeedCoupons()).filter((coupon) => coupon.poi_id === poiId);
}

export const getCouponsForPoi = searchCouponsByPoi;
