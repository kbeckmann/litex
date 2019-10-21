#ifndef __BOOT_H
#define __BOOT_H

int serialboot(void);
void netboot(void);
void flashboot(void);
void romboot(void);
void spiflashboot(char *addr);

#endif /* __BOOT_H */
